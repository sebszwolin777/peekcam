"""Settings dialog: pick source + resolution/fps/format, and adjust every v4l2 control
the selected camera reports. Control widgets are generated dynamically from
v4l2_controls.list_controls so the panel matches each camera exactly.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider,
                             QVBoxLayout, QWidget)

from . import device_manager, v4l2_controls
from .device_manager import Camera


class SettingsDialog(QDialog):
    # emitted when the user chooses a source/format: (device_path, fourcc, w, h, fps)
    format_selected = pyqtSignal(str, str, int, int, float)
    # emitted when a v4l2 control changes: (device_path, name, value)
    control_changed = pyqtSignal(str, str, int)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("PeekCam — Settings")
        self.resize(420, 640)
        self.cameras: list[Camera] = []
        self.current: Camera | None = None

        root = QVBoxLayout(self)

        # --- source / format ------------------------------------------------
        src_box = QGroupBox("Source & format")
        form = QFormLayout(src_box)
        self.cbo_device = QComboBox()
        self.cbo_format = QComboBox()   # fourcc
        self.cbo_size = QComboBox()     # WxH
        self.cbo_fps = QComboBox()
        self.cbo_device.currentIndexChanged.connect(self._on_device_changed)
        self.cbo_format.currentIndexChanged.connect(self._on_format_changed)
        self.cbo_size.currentIndexChanged.connect(self._on_size_changed)
        form.addRow("Camera", self.cbo_device)
        form.addRow("Pixel format", self.cbo_format)
        form.addRow("Resolution", self.cbo_size)
        form.addRow("Frame rate", self.cbo_fps)
        btn_apply = QPushButton("Apply format")
        btn_apply.clicked.connect(self._emit_format)
        form.addRow(btn_apply)
        root.addWidget(src_box)

        # --- dynamic v4l2 controls -----------------------------------------
        ctrl_box = QGroupBox("Camera controls")
        cbl = QVBoxLayout(ctrl_box)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.ctrl_host = QWidget()
        self.ctrl_layout = QFormLayout(self.ctrl_host)
        self.scroll.setWidget(self.ctrl_host)
        cbl.addWidget(self.scroll)
        btn_reset = QPushButton("Reset controls to defaults")
        btn_reset.clicked.connect(self._reset_controls)
        cbl.addWidget(btn_reset)
        root.addWidget(ctrl_box, 1)

        self.refresh_devices()

    # ---------------------------------------------------------------- devices
    def refresh_devices(self) -> None:
        self.cameras = device_manager.list_cameras()
        self.cbo_device.blockSignals(True)
        self.cbo_device.clear()
        for cam in self.cameras:
            self.cbo_device.addItem(f"{cam.name}  ({cam.path})", cam.path)
        self.cbo_device.blockSignals(False)
        if not self.cameras:
            return
        # restore last-used device if possible
        want = self.config.get("device_id")
        idx = 0
        for i, cam in enumerate(self.cameras):
            if cam.device_id == want:
                idx = i
                break
        self.cbo_device.setCurrentIndex(idx)
        self._on_device_changed(idx)

    def _on_device_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.cameras):
            return
        self.current = self.cameras[idx]
        # formats
        self.cbo_format.blockSignals(True)
        self.cbo_format.clear()
        for pf in self.current.formats:
            self.cbo_format.addItem(f"{pf.fourcc} — {pf.description}", pf.fourcc)
        self.cbo_format.blockSignals(False)
        # prefer MJPG for higher res/fps if present
        pref = self.config.get("fourcc")
        fourccs = [pf.fourcc for pf in self.current.formats]
        if pref in fourccs:
            self.cbo_format.setCurrentIndex(fourccs.index(pref))
        elif "MJPG" in fourccs:
            self.cbo_format.setCurrentIndex(fourccs.index("MJPG"))
        self._on_format_changed(self.cbo_format.currentIndex())
        self._build_controls()

    def _on_format_changed(self, _idx: int) -> None:
        if self.current is None:
            return
        pf = self._current_format()
        if pf is None:
            return
        self.cbo_size.blockSignals(True)
        self.cbo_size.clear()
        for s in pf.sizes:
            self.cbo_size.addItem(f"{s.width}x{s.height}", (s.width, s.height))
        self.cbo_size.blockSignals(False)
        # restore size
        want = (self.config.get("width"), self.config.get("height"))
        for i, s in enumerate(pf.sizes):
            if (s.width, s.height) == want:
                self.cbo_size.setCurrentIndex(i)
                break
        self._on_size_changed(self.cbo_size.currentIndex())

    def _on_size_changed(self, idx: int) -> None:
        pf = self._current_format()
        if pf is None or idx < 0 or idx >= len(pf.sizes):
            return
        size = pf.sizes[idx]
        self.cbo_fps.blockSignals(True)
        self.cbo_fps.clear()
        for fps in size.fps:
            self.cbo_fps.addItem(f"{fps:g} fps", fps)
        if not size.fps:
            self.cbo_fps.addItem("30 fps", 30.0)
        self.cbo_fps.blockSignals(False)
        want = self.config.get("fps")
        for i in range(self.cbo_fps.count()):
            if abs(self.cbo_fps.itemData(i) - (want or -1)) < 0.01:
                self.cbo_fps.setCurrentIndex(i)
                break

    def _current_format(self):
        if self.current is None:
            return None
        idx = self.cbo_format.currentIndex()
        if idx < 0 or idx >= len(self.current.formats):
            return None
        return self.current.formats[idx]

    def _emit_format(self) -> None:
        if self.current is None:
            return
        pf = self._current_format()
        size = self.cbo_size.currentData()
        fps = self.cbo_fps.currentData()
        if pf is None or size is None or fps is None:
            return
        w, h = size
        # persist
        self.config["device_id"] = self.current.device_id
        self.config["fourcc"] = pf.fourcc
        self.config["width"] = w
        self.config["height"] = h
        self.config["fps"] = float(fps)
        self.format_selected.emit(self.current.path, pf.fourcc, w, h, float(fps))

    # --------------------------------------------------------------- controls
    def _clear_controls(self) -> None:
        while self.ctrl_layout.count():
            item = self.ctrl_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _build_controls(self) -> None:
        self._clear_controls()
        if self.current is None:
            return
        dev = self.current.path
        controls = v4l2_controls.list_controls(dev)
        saved = self.config.controls_for(self.current.device_id)
        for ctrl in controls:
            if not ctrl.writable:
                continue
            # apply any saved value first so the widget reflects it
            if ctrl.name in saved:
                v4l2_controls.set_control(dev, ctrl.name, int(saved[ctrl.name]))
                ctrl.value = int(saved[ctrl.name])
            widget = self._make_widget(dev, ctrl)
            if widget is not None:
                self.ctrl_layout.addRow(QLabel(ctrl.name.replace("_", " ")), widget)

    def _make_widget(self, dev: str, ctrl: v4l2_controls.Control) -> QWidget | None:
        if ctrl.ctype == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(ctrl.value))
            cb.toggled.connect(lambda on, n=ctrl.name: self._apply(dev, n, 1 if on else 0))
            return cb
        if ctrl.ctype == "menu":
            combo = QComboBox()
            for val, label in sorted(ctrl.menu.items()):
                combo.addItem(label, val)
            # select current
            for i in range(combo.count()):
                if combo.itemData(i) == ctrl.value:
                    combo.setCurrentIndex(i)
                    break
            combo.currentIndexChanged.connect(
                lambda _i, c=combo, n=ctrl.name: self._apply(dev, n, c.currentData()))
            return combo
        if ctrl.ctype in ("int", "int64"):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(ctrl.minimum)
            slider.setMaximum(ctrl.maximum)
            slider.setSingleStep(max(1, ctrl.step))
            slider.setValue(ctrl.value)
            val_lbl = QLabel(str(ctrl.value))
            val_lbl.setMinimumWidth(44)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            slider.valueChanged.connect(
                lambda v, n=ctrl.name, lbl=val_lbl: (lbl.setText(str(v)),
                                                     self._apply(dev, n, v)))
            h.addWidget(slider, 1)
            h.addWidget(val_lbl)
            return row
        return None

    def _apply(self, dev: str, name: str, value: int) -> None:
        v4l2_controls.set_control(dev, name, int(value))
        if self.current is not None:
            self.control_changed.emit(dev, name, int(value))
            self.config.set_control(self.current.device_id, name, int(value))

    def _reset_controls(self) -> None:
        if self.current is None:
            return
        dev = self.current.path
        for ctrl in v4l2_controls.list_controls(dev):
            if ctrl.writable:
                v4l2_controls.set_control(dev, ctrl.name, ctrl.default)
                self.config.set_control(self.current.device_id, ctrl.name, ctrl.default)
        self._build_controls()
