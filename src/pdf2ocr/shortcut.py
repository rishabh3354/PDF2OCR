"""Adding the quick-capture keyboard shortcut to GNOME (via dconf).

Other desktops get instructions instead; their shortcut systems differ too much.
"""

import ast
import os
import subprocess

from .tools import find_tool

BASE = "/org/gnome/settings-daemon/plugins/media-keys/"
LIST_KEY = BASE + "custom-keybindings"
OUR_PATH = BASE + "custom-keybindings/pdf2ocr-capture/"
DEFAULT_SHORTCUT = "Ctrl+Alt+O"

MODIFIERS = {"ctrl": "<Control>", "alt": "<Alt>", "shift": "<Shift>", "meta": "<Super>"}
KEY_NAMES = {"space": "space", "print": "Print", "return": "Return", "tab": "Tab", "esc": "Escape"}


def is_gnome():
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    return any(name in desktop for name in ("gnome", "unity", "pop", "budgie")) and find_tool("dconf") is not None


def to_gnome(sequence):
    """'Ctrl+Alt+O' (Qt portable text) -> '<Control><Alt>o'."""
    parts = sequence.split("+")
    key = parts[-1] if parts[-1] else "+"
    mods = "".join(MODIFIERS.get(part.lower(), "") for part in parts[:-1])
    if len(key) == 1:
        key = key.lower()
    else:
        key = KEY_NAMES.get(key.lower(), key)
    return mods + key


def from_gnome(binding):
    """'<Control><Alt>o' -> 'Ctrl+Alt+O' (best effort, for display)."""
    names = {v: k for k, v in MODIFIERS.items()}
    mods, rest = [], binding
    while rest.startswith("<") and ">" in rest:
        token, rest = rest[:rest.index(">") + 1], rest[rest.index(">") + 1:]
        mods.append({"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Meta"}.get(names.get(token, ""), token))
    return "+".join(mods + [rest.upper() if len(rest) == 1 else rest])


def _dconf(*args):
    proc = subprocess.run([find_tool("dconf") or "dconf"] + list(args), capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise OSError(proc.stderr.strip() or f"dconf exited with {proc.returncode}")
    return proc.stdout.strip()


def _paths():
    raw = _dconf("read", LIST_KEY)
    if not raw:
        return []
    raw = raw[4:] if raw.startswith("@as ") else raw
    try:
        return list(ast.literal_eval(raw))
    except (ValueError, SyntaxError):
        raise OSError("Unexpected shortcut list format.")


def _gvariant_string(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def current_binding():
    """The shortcut we installed earlier, e.g. 'Ctrl+Alt+O', or None."""
    try:
        if OUR_PATH not in _paths():
            return None
        binding = _dconf("read", OUR_PATH + "binding")
    except (OSError, subprocess.SubprocessError):
        return None
    return from_gnome(ast.literal_eval(binding)) if binding else None


def install(sequence, command):
    paths = _paths()
    if OUR_PATH not in paths:
        paths.append(OUR_PATH)
    _dconf("write", OUR_PATH + "name", _gvariant_string("PDF2OCR: capture text from screen"))
    _dconf("write", OUR_PATH + "command", _gvariant_string(command))
    _dconf("write", OUR_PATH + "binding", _gvariant_string(to_gnome(sequence)))
    _dconf("write", LIST_KEY, "[" + ", ".join(_gvariant_string(p) for p in paths) + "]")


def remove():
    paths = [p for p in _paths() if p != OUR_PATH]
    _dconf("write", LIST_KEY, "[" + ", ".join(_gvariant_string(p) for p in paths) + "]" if paths else "@as []")
    _dconf("reset", "-f", OUR_PATH)
