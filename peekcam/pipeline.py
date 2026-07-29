"""GStreamer capture pipeline.

Capture:  v4l2src -> [jpegdec if MJPEG] -> videoconvert -> video/x-raw,format=RGB -> appsink

Each frame is pulled on the GStreamer streaming thread, optionally background-blurred in
Python, handed to the GUI thread as a QImage (queued signal), and — while recording —
pushed into a separate encoder pipeline via appsrc. Recording therefore captures exactly
what's shown on screen (blurred when blur is on), not the raw camera feed.

    appsrc(RGB) -> queue -> videoconvert -> x264enc -> h264parse -> mp4mux -> filesink
"""
from __future__ import annotations

import threading

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib  # noqa: E402

from PyQt6.QtCore import QObject, pyqtSignal, QTimer  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402

from . import device_manager

Gst.init(None)


class CameraPipeline(QObject):
    frame_ready = pyqtSignal(QImage)
    error = pyqtSignal(str)
    recording_changed = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pipeline: Gst.Pipeline | None = None
        self._appsink: Gst.Element | None = None
        self._cur = (0, 0, 30.0)  # width, height, fps of the running capture
        # recording (appsrc encoder pipeline)
        self._rec_lock = threading.Lock()
        self._rec_pipeline: Gst.Pipeline | None = None
        self._rec_appsrc: Gst.Element | None = None
        self._recording = False
        # background blur (optional; lazy)
        self._blur_enabled = False
        self._blur = None
        self._bus_timer = QTimer(self)
        self._bus_timer.setInterval(100)
        self._bus_timer.timeout.connect(self._poll_bus)

    def set_blur_enabled(self, enabled: bool) -> bool:
        """Enable/disable background blur. Returns the resulting state (False if the
        ML stack isn't available). The BackgroundBlur is created lazily on the streaming
        thread in _blur_frame_array() (see blur.py for why isolation matters)."""
        if enabled:
            from . import blur
            if not blur.available():
                self._blur_enabled = False
                return False
        self._blur_enabled = enabled
        self._close_blur()
        return self._blur_enabled

    # ------------------------------------------------------------------ build
    def _build_description(self, device: str, fourcc: str, width: int,
                           height: int, fps: float) -> str:
        num, den = device_manager.fps_fraction(fps)
        rate = f"{num}/{den}"
        if fourcc.upper() in ("MJPG", "JPEG"):
            src_caps = (f"image/jpeg,width={width},height={height},"
                        f"framerate={rate} ! jpegdec")
        else:
            fmt = {"YUYV": "YUY2"}.get(fourcc.upper(), fourcc.upper())
            src_caps = (f"video/x-raw,format={fmt},width={width},height={height},"
                        f"framerate={rate}")
        return (
            f"v4l2src device={device} ! {src_caps} ! videoconvert ! "
            f"video/x-raw,format=RGB ! "
            f"appsink name=disp emit-signals=true max-buffers=2 drop=true sync=false"
        )

    def start(self, device: str, fourcc: str, width: int, height: int, fps: float) -> None:
        self.stop()
        self._cur = (width, height, fps)
        desc = self._build_description(device, fourcc, width, height, fps)
        try:
            self._pipeline = Gst.parse_launch(desc)
        except GLib.Error as e:
            self.error.emit(f"Failed to build pipeline: {e}")
            return
        self._appsink = self._pipeline.get_by_name("disp")
        self._appsink.connect("new-sample", self._on_new_sample)
        self._pipeline.set_state(Gst.State.PLAYING)
        self._bus_timer.start()

    def stop(self) -> None:
        self._bus_timer.stop()
        if self._recording:
            self.stop_recording()
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
        self._appsink = None
        self._close_blur()

    def _close_blur(self) -> None:
        if self._blur is not None:
            try:
                self._blur.close()
            except Exception:
                pass
            self._blur = None

    # --------------------------------------------------------------- frames
    def _on_new_sample(self, sink: Gst.Element) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        struct = sample.get_caps().get_structure(0)
        ok_w, w = struct.get_int("width")
        ok_h, h = struct.get_int("height")
        if not (ok_w and ok_h and h > 0):
            return Gst.FlowReturn.OK
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR
        try:
            stride = mapinfo.size // h  # derive stride so any row padding is handled
            data = bytes(mapinfo.data)
            need_packed = self._recording  # appsrc needs tightly-packed RGB
            if self._blur_enabled:
                packed = self._blur_frame_bytes(data, w, h, stride)
            elif need_packed:
                packed = self._pack_rgb(data, w, h, stride)
            else:
                packed = None
            if packed is not None:
                img = QImage(packed, w, h, w * 3, QImage.Format.Format_RGB888).copy()
            else:
                img = QImage(data, w, h, stride, QImage.Format.Format_RGB888).copy()
        finally:
            buf.unmap(mapinfo)
        self.frame_ready.emit(img)
        if self._recording and packed is not None:
            self._push_record_frame(packed, w, h)
        return Gst.FlowReturn.OK

    @staticmethod
    def _pack_rgb(data: bytes, w: int, h: int, stride: int) -> bytes:
        if stride == w * 3:
            return data
        import numpy as np
        arr = np.frombuffer(data, dtype=np.uint8)[:h * stride].reshape(h, stride)[:, : w * 3]
        return arr.tobytes()

    def _blur_frame_bytes(self, data: bytes, w: int, h: int, stride: int) -> bytes:
        """Blur a frame and return tightly-packed RGB bytes; fall back to raw on error.

        Runs on the streaming thread; BackgroundBlur is created here (once) so its worker
        subprocess is owned by this thread's flow.
        """
        try:
            import numpy as np
            if self._blur is None:
                from . import blur
                self._blur = blur.BackgroundBlur()
            arr = np.frombuffer(data, dtype=np.uint8)
            arr = arr[:h * stride].reshape(h, stride)[:, : w * 3].reshape(h, w, 3)
            out = np.ascontiguousarray(self._blur.process(np.ascontiguousarray(arr)))
            return out.tobytes()
        except Exception as e:  # never let a bad frame kill capture
            self.error.emit(f"blur error: {e}")
            self._blur_enabled = False
            self._close_blur()
            return self._pack_rgb(data, w, h, stride)

    # ------------------------------------------------------------ recording
    def start_recording(self, path: str) -> None:
        if self._pipeline is None or self._recording:
            return
        w, h, fps = self._cur
        if w == 0 or h == 0:
            return
        num, den = device_manager.fps_fraction(fps)
        caps_str = f"video/x-raw,format=RGB,width={w},height={h},framerate={num}/{den}"
        desc = (
            f"appsrc name=src is-live=true do-timestamp=true format=time block=false "
            f"max-bytes=0 ! {caps_str} ! queue max-size-buffers=8 leaky=downstream ! "
            f"videoconvert ! x264enc tune=zerolatency speed-preset=veryfast ! "
            f"h264parse ! mp4mux ! filesink name=fsink async=false"
        )
        try:
            rec = Gst.parse_launch(desc)
        except GLib.Error as e:
            self.error.emit(f"Failed to build recorder: {e}")
            return
        appsrc = rec.get_by_name("src")
        appsrc.set_property("caps", Gst.Caps.from_string(caps_str))
        rec.get_by_name("fsink").set_property("location", path)
        rec.set_state(Gst.State.PLAYING)
        with self._rec_lock:
            self._rec_pipeline = rec
            self._rec_appsrc = appsrc
            self._recording = True
        self.recording_changed.emit(True)

    def _push_record_frame(self, packed: bytes, w: int, h: int) -> None:
        with self._rec_lock:
            if not self._recording or self._rec_appsrc is None:
                return
            if len(packed) != w * h * 3:
                return  # size changed mid-recording; skip
            self._rec_appsrc.emit("push-buffer", Gst.Buffer.new_wrapped(packed))

    def stop_recording(self) -> None:
        with self._rec_lock:
            if not self._recording:
                return
            self._recording = False
            rec, appsrc = self._rec_pipeline, self._rec_appsrc
            self._rec_pipeline = self._rec_appsrc = None
        # finalize outside the lock so a valid moov atom is written
        if appsrc is not None:
            appsrc.emit("end-of-stream")
        if rec is not None:
            rec.get_bus().timed_pop_filtered(
                3 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            rec.set_state(Gst.State.NULL)
        self.recording_changed.emit(False)

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ----------------------------------------------------------------- bus
    def _poll_bus(self) -> None:
        if self._pipeline is None:
            return
        bus = self._pipeline.get_bus()
        while True:
            msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
            if msg is None:
                break
            if msg.type == Gst.MessageType.ERROR:
                err, dbg = msg.parse_error()
                self.error.emit(f"{err.message} ({dbg})")
            elif msg.type == Gst.MessageType.EOS:
                self.error.emit("End of stream")
