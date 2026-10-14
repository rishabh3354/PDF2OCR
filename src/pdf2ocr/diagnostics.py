"""A plain-text system report users can paste into a bug report."""

import os
import platform
import subprocess
import sys

from . import __version__
from .tools import find_tool, tesseract_version

LOG_LINES = 40


def log_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "pdf2ocr", "pdf2ocr.log")


def _tool_version(name, *args):
    exe = find_tool(name)
    if not exe:
        return "not installed"
    try:
        proc = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        return f"error: {error}"
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return lines[0].strip() if lines else "unknown"


def _os_name():
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.platform()


def _versions():
    from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    result = {"Python": platform.python_version(), "PyQt": PYQT_VERSION_STR, "Qt": QT_VERSION_STR}
    for module in ("PIL", "pypdf"):
        try:
            result[module] = __import__(module).__version__
        except Exception:  # noqa: BLE001 - report whatever we can
            result[module] = "not installed"
    return result


def collect(store=None, settings=None):
    from PyQt5.QtGui import QGuiApplication

    lines = [f"PDF2OCR {__version__}", ""]

    def section(title, rows):
        lines.append(f"[{title}]")
        lines.extend(f"  {key}: {value}" for key, value in rows)
        lines.append("")

    app = QGuiApplication.instance()
    screens = []
    if app:
        for screen in QGuiApplication.screens():
            size = screen.size()
            screens.append(f"{size.width()}x{size.height()} @{screen.devicePixelRatio():g}x")
    section("System", [
        ("OS", _os_name()), ("Kernel", platform.release()), ("Architecture", platform.machine()),
        ("Desktop", os.environ.get("XDG_CURRENT_DESKTOP", "unknown")),
        ("Session", os.environ.get("XDG_SESSION_TYPE", "unknown")),
        ("Qt platform", QGuiApplication.platformName() if app else "n/a"),
        ("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "(not set)")),
        ("Screens", ", ".join(screens) or "n/a"),
        ("Snap", f"{os.environ.get('SNAP_VERSION')} (revision {os.environ.get('SNAP_REVISION')})"
         if os.environ.get("SNAP") else "no (running from source)"),
    ])
    section("Libraries", list(_versions().items()) + [("Python executable", sys.executable)])
    section("Tools", [
        ("Tesseract", tesseract_version() or "not installed"),
        ("pdftoppm", _tool_version("pdftoppm", "-v")),
        ("scanimage", _tool_version("scanimage", "--version")),
    ])
    if store is not None:
        section("Languages", [
            ("Installed", ", ".join(store.installed()) or "none"),
            ("Orientation detection (osd)", "yes" if store.has_osd() else "no"),
            ("Bundled data", store.bundled_dir or "not found"),
            ("Data folder used", store.tessdata_dir or "tesseract default"),
        ])
    if settings is not None:
        keys = ["ocr/languages", "ocr/page_layout", "ocr/pdf_dpi", "ocr/use_text_layer", "ocr/parallel_pages",
                "image/auto_rotate", "image/upscale_small", "image/improve_contrast", "image/black_and_white",
                "image/remove_noise", "ui/theme", "ui/restore_session"]
        section("Settings", [(key, settings.get(key)) for key in keys])

    lines.append(f"[Recent log: {log_path()}]")
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as handle:
            tail = handle.read().splitlines()[-LOG_LINES:]
        lines.extend("  " + line for line in tail)
    except OSError:
        lines.append("  (no log yet)")
    return "\n".join(lines) + "\n"
