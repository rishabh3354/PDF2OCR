"""Capturing part of the screen for OCR.

The preferred route is the XDG desktop portal (works on Wayland, inside the snap
sandbox, and lets the desktop show its own region picker). On plain X11 without
a portal we grab the screen ourselves and show a simple region selector.
"""

import logging
import os
import uuid

from PyQt5.QtCore import QObject, QPoint, QRect, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)

try:
    from PyQt5.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
except ImportError:
    QDBusConnection = None

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


class ScreenCapture(QObject):
    """Emits captured(path) with a PNG file, or failed(message), or nothing on cancel."""

    captured = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, window, workdir):
        """window is minimized during the capture; pass None in quick-capture mode."""
        super().__init__(window)
        self.window = window
        self.workdir = workdir
        self._selector = None
        self._request_path = None

    def start(self):
        if self.window is None:
            QTimer.singleShot(0, self._capture)
            return
        self.window.showMinimized()
        # Give the compositor a moment to actually hide our window.
        QTimer.singleShot(450, self._capture)

    def _capture(self):
        if self._start_portal():
            return
        if os.environ.get("XDG_SESSION_TYPE") != "wayland" and QGuiApplication.primaryScreen():
            self._start_x11()
            return
        self._fail("Screen capture isn't available on this desktop. Take a screenshot with your "
                   "system tool (for example Shift+PrtSc copies an area to the clipboard) and "
                   "press Ctrl+V here.")

    # ---- XDG desktop portal ------------------------------------------------

    def _start_portal(self):
        if QDBusConnection is None:
            return False
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False
        token = "pdf2ocr_" + uuid.uuid4().hex[:12]
        sender = bus.baseService().lstrip(":").replace(".", "_")
        self._request_path = f"{PORTAL_PATH}/request/{sender}/{token}"
        # Subscribe before calling so we can't miss a fast response.
        if not bus.connect(PORTAL_SERVICE, self._request_path, "org.freedesktop.portal.Request",
                           "Response", self._portal_response):
            return False
        portal = QDBusInterface(PORTAL_SERVICE, PORTAL_PATH, "org.freedesktop.portal.Screenshot", bus)
        if not portal.isValid():
            self._disconnect_portal()
            return False
        reply = portal.call("Screenshot", "", {"handle_token": token, "interactive": True})
        if reply.type() == QDBusMessage.ErrorMessage:
            log.warning("Screenshot portal error: %s", reply.errorMessage())
            self._disconnect_portal()
            return False
        return True

    def _disconnect_portal(self):
        if self._request_path:
            QDBusConnection.sessionBus().disconnect(PORTAL_SERVICE, self._request_path,
                                                    "org.freedesktop.portal.Request", "Response",
                                                    self._portal_response)
            self._request_path = None

    @pyqtSlot(QDBusMessage if QDBusConnection else object)
    def _portal_response(self, message):
        self._disconnect_portal()
        arguments = message.arguments()
        code = arguments[0] if arguments else 2
        results = arguments[1] if len(arguments) > 1 else {}
        uri = results.get("uri") if isinstance(results, dict) else None
        if code == 0 and uri:
            path = QUrl(uri).toLocalFile()
            self._done(path)
        elif code == 1:
            self._done(None)  # user cancelled
        else:
            self._fail("The screenshot could not be taken.")

    # ---- X11 fallback --------------------------------------------------------

    def _start_x11(self):
        screen = QGuiApplication.screenAt(QApplication.desktop().cursor().pos()) or QGuiApplication.primaryScreen()
        shot = screen.grabWindow(0)
        if shot.isNull():
            self._fail("The screen could not be captured.")
            return
        self._selector = RegionSelector(shot, screen.geometry())
        self._selector.selected.connect(self._region_selected)
        self._selector.show()

    def _region_selected(self, pixmap):
        self._selector = None
        if pixmap is None or pixmap.isNull():
            self._done(None)
            return
        path = os.path.join(self.workdir, f"screenshot-{uuid.uuid4().hex[:8]}.png")
        pixmap.save(path, "PNG")
        self._done(path)

    # ---- completion ----------------------------------------------------------

    def _restore(self):
        if self.window is None:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _done(self, path):
        self._restore()
        if path:
            self.captured.emit(path)
        self.finished.emit()

    def _fail(self, message):
        self._restore()
        self.failed.emit(message)
        self.finished.emit()


class RegionSelector(QWidget):
    selected = pyqtSignal(object)

    def __init__(self, pixmap, geometry):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.pixmap = pixmap
        self.setGeometry(geometry)
        self.setCursor(Qt.CrossCursor)
        self.origin = self.current = None
        self.showFullScreen()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect().adjusted(0, 24, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                         "Drag to select the text area  ·  Esc to cancel")
        if self.origin and self.current:
            rect = QRect(self.origin, self.current).normalized()
            ratio = self.pixmap.devicePixelRatio()
            source = QRect(int(rect.x() * ratio), int(rect.y() * ratio),
                           int(rect.width() * ratio), int(rect.height() * ratio))
            painter.drawPixmap(rect, self.pixmap, source)
            painter.setPen(QPen(QColor("#7090FF"), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.origin = self.current = event.pos()

    def mouseMoveEvent(self, event):
        self.current = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        rect = QRect(self.origin or QPoint(), event.pos()).normalized()
        ratio = self.pixmap.devicePixelRatio()
        result = None
        if rect.width() > 5 and rect.height() > 5:
            result = self.pixmap.copy(QRect(int(rect.x() * ratio), int(rect.y() * ratio),
                                            int(rect.width() * ratio), int(rect.height() * ratio)))
        self.close()
        self.selected.emit(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            self.selected.emit(None)
