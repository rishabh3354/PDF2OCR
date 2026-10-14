"""The welcome screen shown before any document is opened."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import theme
from .widgets import repolish


class EmptyState(QWidget):
    open_clicked = pyqtSignal()
    paste_clicked = pyqtSignal()
    screenshot_clicked = pyqtSignal()
    scan_clicked = pyqtSignal()
    url_clicked = pyqtSignal()
    languages_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)

        self.zone = QFrame()
        self.zone.setObjectName("DropZone")
        self.zone.setMaximumWidth(720)
        self.zone.setMinimumHeight(380)
        zone = QVBoxLayout(self.zone)
        zone.setContentsMargins(40, 40, 40, 36)
        zone.setSpacing(10)
        zone.addStretch(1)

        self.hero_icon = QLabel()
        self.hero_icon.setAlignment(Qt.AlignCenter)
        title = QLabel("Turn documents into editable text")
        title.setObjectName("HeroTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Drop PDFs, scans or images here, or choose a way to start below.")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        zone.addWidget(self.hero_icon)
        zone.addWidget(title)
        zone.addWidget(subtitle)
        zone.addSpacing(14)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        self.open_button = self._button("Open files", "open", self.open_clicked, primary=True)
        self.paste_button = self._button("Paste image", "paste", self.paste_clicked)
        self.shot_button = self._button("Screenshot", "screenshot", self.screenshot_clicked)
        self.scan_button = self._button("Scan", "scanner", self.scan_clicked)
        for button in (self.open_button, self.paste_button, self.shot_button, self.scan_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        zone.addLayout(buttons)

        url = QPushButton("or open a file from a web address")
        url.setObjectName("Link")
        url.setCursor(Qt.PointingHandCursor)
        url.clicked.connect(self.url_clicked)
        zone.addWidget(url, 0, Qt.AlignHCenter)
        zone.addStretch(1)

        self.language_line = QPushButton()
        self.language_line.setObjectName("Link")
        self.language_line.setCursor(Qt.PointingHandCursor)
        self.language_line.clicked.connect(self.languages_clicked)
        zone.addWidget(self.language_line, 0, Qt.AlignHCenter)

        privacy = QHBoxLayout()
        privacy.addStretch(1)
        self.lock_icon = QLabel()
        privacy_text = QLabel("Runs 100% offline on your computer with Tesseract OCR. "
                              "Files are never uploaded.")
        privacy_text.setObjectName("Muted")
        privacy.addWidget(self.lock_icon)
        privacy.addWidget(privacy_text)
        privacy.addStretch(1)
        zone.addLayout(privacy)

        formats = QLabel("PDF · PNG · JPG · TIFF (multi-page) · BMP · GIF · WebP")
        formats.setObjectName("Faint")
        formats.setAlignment(Qt.AlignCenter)
        zone.addWidget(formats)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.zone, 10)
        row.addStretch(1)
        outer.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.refresh_icons()

    def _button(self, text, icon, signal, primary=False):
        button = QPushButton(f" {text}")
        button.setProperty("iconName", icon)
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(38)
        if primary:
            button.setObjectName("Primary")
        else:
            button.setProperty("outlined", True)
        button.clicked.connect(signal)
        return button

    def refresh_icons(self):
        c = theme().colors
        self.hero_icon.setPixmap(theme().pixmap("document", c["accent"], 56))
        self.lock_icon.setPixmap(theme().pixmap("lock", c["success"], 14))
        self.open_button.setIcon(theme().icon("open", color=c["accent_text"], size=18))
        self.paste_button.setIcon(theme().icon("paste", size=18))
        self.shot_button.setIcon(theme().icon("screenshot", size=18))
        self.scan_button.setIcon(theme().icon("scanner", size=18))

    def set_languages(self, text):
        self.language_line.setText(f"Text language: {text}  ·  change")

    def set_drag_active(self, active):
        self.zone.setProperty("active", active)
        repolish(self.zone)
