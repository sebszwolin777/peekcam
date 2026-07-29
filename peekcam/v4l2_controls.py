"""Dynamic v4l2 control discovery and application via v4l2-ctl.

`list_controls` parses `--list-ctrls-menus` into typed descriptors so the settings
panel can build itself from whatever the selected camera actually reports.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class Control:
    name: str                       # e.g. "brightness"
    ctype: str                      # "int" | "bool" | "menu" | "button" | "int64" | "unknown"
    minimum: int = 0
    maximum: int = 0
    step: int = 1
    default: int = 0
    value: int = 0
    flags: str = ""                 # e.g. "inactive", "read-only"
    menu: dict[int, str] = field(default_factory=dict)  # value -> label

    @property
    def writable(self) -> bool:
        return "read-only" not in self.flags and self.ctype != "button"


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=5).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


# Matches lines like:
#   brightness 0x00980900 (int)    : min=-64 max=64 step=1 default=0 value=0
#   white_balance_automatic 0x0098090c (bool)   : default=1 value=1
#   power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=1 value=1 flags=...
_CTRL_RE = re.compile(
    r"^\s*(?P<name>\w+)\s+0x[0-9a-fA-F]+\s+\((?P<type>\w+)\)\s*:\s*(?P<rest>.*)$"
)
_MENU_ITEM_RE = re.compile(r"^\s*(\d+):\s*(.+?)\s*$")


def _parse_kv(rest: str) -> dict[str, str]:
    kv: dict[str, str] = {}
    for m in re.finditer(r"(\w+)=(-?\S+)", rest):
        kv[m.group(1)] = m.group(2)
    # flags may appear as "flags=inactive" or trailing words
    fm = re.search(r"flags=([\w,\- ]+)", rest)
    if fm:
        kv["flags"] = fm.group(1).strip()
    return kv


def list_controls(device: str) -> list[Control]:
    out = _run(["v4l2-ctl", "-d", device, "--list-ctrls-menus"])
    controls: list[Control] = []
    cur: Control | None = None
    for line in out.splitlines():
        mc = _CTRL_RE.match(line)
        if mc:
            kv = _parse_kv(mc.group("rest"))
            cur = Control(
                name=mc.group("name"),
                ctype=mc.group("type"),
                minimum=int(kv.get("min", 0)),
                maximum=int(kv.get("max", 0)),
                step=int(kv.get("step", 1)),
                default=int(kv.get("default", 0)),
                value=int(kv.get("value", 0)),
                flags=kv.get("flags", ""),
            )
            controls.append(cur)
            continue
        # menu items are indented under the owning menu control
        mm = _MENU_ITEM_RE.match(line)
        if mm and cur is not None and cur.ctype == "menu":
            cur.menu[int(mm.group(1))] = mm.group(2)
    return controls


def set_control(device: str, name: str, value: int) -> bool:
    try:
        r = subprocess.run(
            ["v4l2-ctl", "-d", device, "--set-ctrl", f"{name}={value}"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_control(device: str, name: str) -> int | None:
    out = _run(["v4l2-ctl", "-d", device, "--get-ctrl", name])
    m = re.search(rf"{re.escape(name)}:\s*(-?\d+)", out)
    return int(m.group(1)) if m else None


def apply_all(device: str, values: dict[str, int]) -> None:
    for name, value in values.items():
        set_control(device, name, int(value))
