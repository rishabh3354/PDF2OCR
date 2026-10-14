"""Application start-up: platform fixes, logging, crash reporting."""

import atexit
import glob
import logging
import logging.handlers
import os
import shutil
import sys
import tempfile
import traceback


def _log_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "pdf2ocr")
    os.makedirs(path, exist_ok=True)
    return path


def setup_logging():
    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.handlers.RotatingFileHandler(
            os.path.join(_log_dir(), "pdf2ocr.log"), maxBytes=512 * 1024, backupCount=1))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def fix_qt_platform():
    """Avoid “could not find or load the Qt platform plugin "wayland-egl"”.

    Many desktops export QT_QPA_PLATFORM=wayland(-egl) globally, but the Qt
    runtime bundled with the snap (and some distro builds) has no Wayland plugin,
    so Qt aborts before showing a window. Fall back to X11/XWayland instead.
    """
    from PyQt5.QtCore import QLibraryInfo

    requested = os.environ.get("QT_QPA_PLATFORM", "")
    if os.environ.get("SNAP"):
        if not requested or "wayland" in requested:
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        return
    if not requested:
        return
    dirs = [os.path.join(QLibraryInfo.location(QLibraryInfo.PluginsPath), "platforms")]
    dirs += [os.path.join(p, "platforms") for p in os.environ.get("QT_PLUGIN_PATH", "").split(":") if p]
    plugins = " ".join(os.path.basename(f) for d in dirs for f in glob.glob(os.path.join(d, "*.so")))
    wanted = [name.split(":")[0] for name in requested.split(";") if name]
    if not any(name in plugins for name in wanted):
        logging.warning("Qt platform '%s' is not available, using xcb", requested)
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def install_excepthook():
    from PyQt5.QtWidgets import QApplication, QMessageBox

    def hook(exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error("Unhandled exception:\n%s", details)
        if QApplication.instance():
            box = QMessageBox(QMessageBox.Warning, "Something went wrong",
                              "PDF2OCR hit an unexpected error. Your work is still open; "
                              "you can keep going or save what you have.\n\n"
                              f"A log was written to {os.path.join(_log_dir(), 'pdf2ocr.log')}")
            box.setDetailedText(details)
            box.exec_()

    sys.excepthook = hook


def _icon_path():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (os.path.join(here, "icons", "pdf2go.png"), os.path.join(here, "pdf2go.png")):
        if os.path.exists(candidate):
            return candidate
    return None


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from .cli import is_cli
    if is_cli(argv[1:]):
        # Batch conversion: no window and no display needed.
        from .cli import main as cli_main
        return cli_main(argv[1:])
    setup_logging()
    fix_qt_platform()
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    from . import APP_ID, APP_NAME, ORG_NAME, __version__

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    install_excepthook()

    from .languages import LanguageStore
    from .settings import Settings
    from .ui.main_window import MainWindow
    from .ui.theme import init_theme

    settings = Settings()
    init_theme().apply(settings.get("ui/theme"))

    workdir = tempfile.mkdtemp(prefix="pdf2ocr-")
    atexit.register(shutil.rmtree, workdir, True)

    store = LanguageStore()
    logging.info("PDF2OCR %s, tessdata=%s, languages=%s", __version__, store.tessdata_dir, store.installed())

    args = argv[1:]
    if "--capture" in args:
        return _quick_capture(app, settings, store, workdir, args)

    window = MainWindow(settings, store, workdir, _icon_path())
    window.show()
    files = [arg for arg in args if not arg.startswith("-")]
    if files:
        window.add_files(files)
    return app.exec_()


def _quick_capture(app, settings, store, workdir, args):
    """`pdf2go --capture [--lang deu+eng]`: screen area -> text on the clipboard."""
    from PyQt5.QtCore import QLocale

    from .languages import default_languages
    from .quick_capture import QuickCapture
    from .ui.main_window import MainWindow

    installed = store.installed()
    languages = [code for code in settings.get("ocr/languages") if code in installed]
    if "--lang" in args and args.index("--lang") + 1 < len(args):
        requested = args[args.index("--lang") + 1].split("+")
        languages = [code for code in requested if code in installed] or languages
    languages = languages or default_languages(installed, QLocale.system().name())

    windows = []

    def open_app(path):
        # "Open in PDF2OCR": become the normal app, with the capture as a page.
        app.setQuitOnLastWindowClosed(True)
        window = MainWindow(settings, store, workdir, _icon_path())
        window.show()
        window.add_files([path], {path: "Screen capture"})
        windows.append(window)

    app.setQuitOnLastWindowClosed(False)
    capture = QuickCapture(settings, store, workdir, languages, open_app, _icon_path())
    capture.start()
    return app.exec_()
