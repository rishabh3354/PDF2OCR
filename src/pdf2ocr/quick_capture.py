"""Quick capture: `pdf2go --capture` selects a screen area, recognizes it and
copies the text to the clipboard without opening the main window.

On Linux the clipboard is owned by the program that copied, so after copying
we stay alive in the background (invisible) until something else is copied,
with a time limit, instead of exiting and losing the text.
"""

import os
import shlex
import sys

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor, QGuiApplication, QPixmap
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .engine import PageJob, recognize
from .jobs import BackgroundCall
from .screenshot import ScreenCapture
from .ui.widgets import tool_button

TOAST_SECONDS = 8
KEEP_CLIPBOARD_MINUTES = 30


def capture_command():
    """The command a desktop keyboard shortcut should run."""
    if os.environ.get("SNAP"):
        return "/snap/bin/pdf2go --capture"
    launcher = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pdf2go.py")
    return f"{shlex.quote(sys.executable)} {shlex.quote(launcher)} --capture"


class Toast(QWidget):
    """A small card in the top-right corner of the screen."""

    open_clicked = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, icon_path=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(380)
        card = QFrame(self)
        card.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 8, 12)
        layout.setSpacing(6)
        header = QHBoxLayout()
        logo = QLabel()
        if icon_path and os.path.exists(icon_path):
            logo.setPixmap(QPixmap(icon_path).scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        app = QLabel("PDF2OCR")
        app.setObjectName("Muted")
        close = tool_button("close", "Close", size=14)
        close.clicked.connect(self.dismiss)
        header.addWidget(logo)
        header.addWidget(app, 1)
        header.addWidget(close)
        layout.addLayout(header)

        self.status = QLabel()
        self.status.setObjectName("PanelTitle")
        self.preview = QLabel()
        self.preview.setObjectName("Muted")
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 4, 6, 0)
        buttons.addStretch(1)
        self.open_button = QPushButton("Open in PDF2OCR")
        self.open_button.setProperty("outlined", True)
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self.open_clicked)
        buttons.addWidget(self.open_button)
        layout.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)

    def show_busy(self, text):
        self.status.setText(text)
        self.preview.hide()
        self.open_button.hide()
        self._show()

    def show_result(self, status, preview="", can_open=True):
        self.status.setText(status)
        self.preview.setText(preview)
        self.preview.setVisible(bool(preview))
        self.open_button.setVisible(can_open)
        self._show()
        self.timer.start(TOAST_SECONDS * 1000)

    def _show(self):
        self.adjustSize()
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 16, area.top() + 16)
        self.show()
        self.raise_()

    def enterEvent(self, event):
        self.timer.stop()  # keep it open while the mouse is over it
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.open_button.isVisible() or self.preview.isVisible():
            self.timer.start(3000)
        super().leaveEvent(event)

    def dismiss(self):
        self.timer.stop()
        if self.isVisible():
            self.hide()
            self.closed.emit()


def _preview(text, lines=4, width=60):
    rows = [line for line in text.splitlines() if line.strip()]
    shown = [row if len(row) <= width else row[:width - 1] + "…" for row in rows[:lines]]
    if len(rows) > lines:
        shown.append(f"… and {len(rows) - lines} more line{'s' if len(rows) - lines > 1 else ''}")
    return "\n".join(shown)


class QuickCapture(QObject):
    """Runs one capture. open_app(path) turns this process into the full app."""

    def __init__(self, settings, store, workdir, languages, open_app, icon_path=None):
        super().__init__()
        self.settings = settings
        self.store = store
        self.workdir = workdir
        self.languages = languages
        self.open_app = open_app
        self.path = None
        self.copied = None
        self.opened = False
        self.call = None
        self.toast = Toast(icon_path)
        self.toast.open_clicked.connect(self._open)
        self.toast.closed.connect(self._toast_closed)
        self.capture = ScreenCapture(None, workdir)
        self.capture.captured.connect(self._captured)
        self.capture.failed.connect(lambda message: self.toast.show_result("Screen capture failed", message,
                                                                           can_open=False))
        self.capture.finished.connect(self._capture_finished)

    def start(self):
        self.capture.start()

    def _capture_finished(self):
        if self.path is None and not self.toast.isVisible():
            QApplication.quit()  # the user cancelled the selection

    def _captured(self, path):
        self.path = path
        self.toast.show_busy("Reading text…")
        options = self.settings.ocr_options(self.store, self.languages)
        job = PageJob(0, "image", path, 0, 0, False)
        workdir = self.workdir
        self.call = BackgroundCall(lambda _p, token: recognize(job, options, workdir, token), self)
        self.call.finished.connect(self._recognized)
        self.call.failed.connect(lambda message: self.toast.show_result("Couldn't read the text", message))
        self.call.start()

    def _recognized(self, result):
        text = result.text.strip()
        if not text:
            self.toast.show_result("No text found",
                                   "Try selecting a larger area, or open it in PDF2OCR to adjust settings.")
            return
        QApplication.clipboard().setText(text)
        self.copied = text
        words = len(text.split())
        self.toast.show_result(f"Copied {words} word{'s' if words != 1 else ''} to the clipboard", _preview(text))

    def _open(self):
        self.opened = True
        self.toast.dismiss()
        if self.path:
            self.open_app(self.path)

    def _toast_closed(self):
        if self.opened:
            return
        if not self.copied:
            QApplication.quit()
            return
        # Keep owning the clipboard until the user copies something else.
        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
        QTimer.singleShot(KEEP_CLIPBOARD_MINUTES * 60 * 1000, QApplication.quit)

    def _clipboard_changed(self):
        if QApplication.clipboard().text() != self.copied and not self.opened:
            QApplication.quit()
