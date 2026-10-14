"""Settings and About dialogs."""

import os
import webbrowser

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from .. import APP_NAME, DONATE_URL, FEEDBACK_URL, SNAP_STORE_URL, WEBSITE_URL, __version__
from ..engine import PAGE_LAYOUTS
from ..diagnostics import collect as collect_diagnostics, log_path
from ..tools import tesseract_version
from .theme import theme


def _check(text, tooltip=None):
    box = QCheckBox(text)
    if tooltip:
        box.setToolTip(tooltip)
    return box


class SettingsDialog(QDialog):
    def __init__(self, settings, has_osd, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.resize(560, 640)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(18, 8, 18, 8)
        body.setSpacing(12)

        # Recognition
        recognition = QGroupBox("Recognition")
        form = QFormLayout(recognition)
        form.setLabelAlignment(Qt.AlignLeft)
        self.layout_combo = QComboBox()
        for value, label in PAGE_LAYOUTS:
            self.layout_combo.addItem(label, value)
        self.layout_combo.setToolTip("How text is arranged on the page. “Automatic” works for most documents; "
                                     "“Scattered text” helps with receipts and forms.")
        self.dpi_combo = QComboBox()
        for value, label in [(200, "200 DPI · fastest"), (300, "300 DPI · recommended"),
                             (400, "400 DPI · small print"), (600, "600 DPI · tiny print, slow")]:
            self.dpi_combo.addItem(label, value)
        self.dpi_combo.setToolTip("Resolution used when converting scanned PDF pages to images for OCR.")
        self.parallel = QComboBox()
        for count in range(1, max(1, os.cpu_count() or 1) + 1):
            self.parallel.addItem(f"{count} at a time", count)
        self.parallel.setToolTip("How many pages are recognized simultaneously. Higher is faster but uses more CPU.")
        self.text_layer = _check("Use existing text in PDFs when available",
                                 "Digital PDFs already contain exact text. Copying it is instant and "
                                 "100% accurate; OCR is only used for scanned pages.")
        self.auto_start = _check("Start recognizing as soon as files are opened")
        self.preserve_spaces = _check("Keep spacing between words (tables and columns)")
        form.addRow("Page layout", self.layout_combo)
        form.addRow("Scan resolution", self.dpi_combo)
        form.addRow("Pages", self.parallel)
        form.addRow(self.text_layer)
        form.addRow(self.auto_start)
        form.addRow(self.preserve_spaces)
        body.addWidget(recognition)

        # Image cleanup
        cleanup = QGroupBox("Image cleanup")
        box = QVBoxLayout(cleanup)
        self.auto_rotate = _check("Straighten sideways and upside-down pages",
                                  "Detects page orientation and rotates it before recognition.")
        self.auto_rotate.setEnabled(has_osd)
        self.deskew = _check("Straighten slightly tilted pages",
                             "Corrects scans that were placed a little crooked (up to 10°).")
        self.upscale = _check("Enlarge small images and screenshots",
                              "Small text is recognized much better after enlarging.")
        self.contrast = _check("Improve contrast (faded or grey scans)")
        self.bw = _check("Convert to black && white (uneven backgrounds, coloured paper)")
        self.denoise = _check("Remove specks and noise (fax, photocopies)")
        for widget in (self.auto_rotate, self.deskew, self.upscale, self.contrast, self.bw, self.denoise):
            box.addWidget(widget)
        body.addWidget(cleanup)

        # Results
        results = QGroupBox("Results")
        form = QFormLayout(results)
        self.highlight = _check("Underline words that may be misread")
        self.threshold = QComboBox()
        for value in (50, 60, 70, 80, 90):
            self.threshold.addItem(f"below {value}% confidence", value)
        self.separators = _check("Add page headings when exporting text")
        self.area_copy = _check("Copy text from a selected area to the clipboard automatically")
        form.addRow(self.highlight)
        form.addRow("Underline words", self.threshold)
        form.addRow(self.separators)
        form.addRow(self.area_copy)
        body.addWidget(results)

        # Appearance
        appearance = QGroupBox("General")
        form = QFormLayout(appearance)
        self.restore = _check("Reopen documents and their text next time",
                              "Your work is saved automatically and survives closing the app or a crash.\n"
                              "It is kept in your home folder until you close the documents.")
        form.addRow(self.restore)
        self.theme_combo = QComboBox()
        for value, label in [("system", "Follow system"), ("light", "Light"), ("dark", "Dark")]:
            self.theme_combo.addItem(label, value)
        form.addRow("Theme", self.theme_combo)
        body.addWidget(appearance)
        body.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 12)
        layout.addWidget(scroll, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(18, 0, 18, 0)
        footer.addWidget(buttons)
        layout.addLayout(footer)
        self._load(self.settings.get)

    def _fields(self):
        return [
            ("ocr/use_text_layer", self.text_layer), ("ocr/auto_start", self.auto_start),
            ("ocr/preserve_spaces", self.preserve_spaces), ("image/auto_rotate", self.auto_rotate),
            ("image/upscale_small", self.upscale), ("image/deskew", self.deskew), ("image/improve_contrast", self.contrast),
            ("image/black_and_white", self.bw), ("image/remove_noise", self.denoise),
            ("results/highlight_uncertain", self.highlight), ("results/page_separators", self.separators),
            ("results/area_auto_copy", self.area_copy), ("ui/restore_session", self.restore),
        ]

    def _load(self, get):
        for key, box in self._fields():
            box.setChecked(get(key))
        self._select(self.layout_combo, get("ocr/page_layout"))
        self._select(self.dpi_combo, get("ocr/pdf_dpi"))
        self._select(self.theme_combo, get("ui/theme"))
        self._select(self.parallel, get("ocr/parallel_pages"))
        self._select(self.threshold, get("results/uncertain_below"))

    def _restore_defaults(self):
        from ..settings import DEFAULTS
        self._load(DEFAULTS.get)

    @staticmethod
    def _select(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def accept(self):
        for key, box in self._fields():
            self.settings.set(key, box.isChecked())
        self.settings.set("ocr/page_layout", self.layout_combo.currentData())
        self.settings.set("ocr/pdf_dpi", self.dpi_combo.currentData())
        self.settings.set("ui/theme", self.theme_combo.currentData())
        self.settings.set("ocr/parallel_pages", self.parallel.currentData())
        self.settings.set("results/uncertain_below", self.threshold.currentData())
        super().accept()


class AboutDialog(QDialog):
    def __init__(self, icon_path, parent=None, store=None, settings=None):
        super().__init__(parent)
        self.store, self.settings = store, settings
        self.setWindowTitle(f"About {APP_NAME}")
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(8)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        if icon_path and os.path.exists(icon_path):
            logo.setPixmap(QPixmap(icon_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        name = QLabel(APP_NAME)
        name.setObjectName("HeroTitle")
        name.setAlignment(Qt.AlignCenter)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("Muted")
        version.setAlignment(Qt.AlignCenter)
        engine = tesseract_version()
        description = QLabel(
            "Turns scanned PDFs, images and screenshots into editable text.<br><br>"
            f"<b>Private by design.</b> Recognition runs entirely on your computer using "
            f"Tesseract OCR{' ' + engine if engine else ''}. Your documents are never uploaded, "
            "and the text is never translated or rewritten.")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)
        description.setTextFormat(Qt.RichText)
        description.setFixedWidth(384)
        for widget in (logo, name, version):
            layout.addWidget(widget)
        layout.addSpacing(8)
        layout.addWidget(description)
        layout.addSpacing(12)

        links = QHBoxLayout()
        for label, icon, url in [("Website", "globe", WEBSITE_URL), ("Rate app", "check", SNAP_STORE_URL),
                                 ("Feedback", "info", FEEDBACK_URL)]:
            button = QPushButton(label)
            button.setIcon(theme().icon(icon, size=16))
            button.setProperty("outlined", True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, u=url: open_url(u))
            links.addWidget(button)
        layout.addLayout(links)

        donate = QPushButton("  Support development")
        donate.setObjectName("Primary")
        donate.setIcon(theme().icon("heart", color=theme().colors["accent_text"], size=16))
        donate.setCursor(Qt.PointingHandCursor)
        donate.clicked.connect(lambda: open_url(DONATE_URL))
        layout.addWidget(donate)
        thanks = QLabel("PDF2OCR is free. Donations keep updates coming.")
        thanks.setObjectName("Faint")
        thanks.setAlignment(Qt.AlignCenter)
        layout.addWidget(thanks)

        layout.addSpacing(6)
        support = QHBoxLayout()
        diagnostics = QPushButton("Copy diagnostics")
        diagnostics.setObjectName("Link")
        diagnostics.setCursor(Qt.PointingHandCursor)
        diagnostics.setToolTip("Copies version and system details plus the recent log, "
                               "to paste into a bug report.")
        diagnostics.clicked.connect(self._copy_diagnostics)
        logs = QPushButton("Open log folder")
        logs.setObjectName("Link")
        logs.setCursor(Qt.PointingHandCursor)
        logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(log_path()))))
        self.copied = QLabel()
        self.copied.setObjectName("Faint")
        support.addStretch(1)
        support.addWidget(diagnostics)
        support.addWidget(logs)
        support.addStretch(1)
        layout.addLayout(support)
        self.copied.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.copied)

    def _copy_diagnostics(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(collect_diagnostics(self.store, self.settings))
        self.copied.setText("Copied. Paste it into your bug report or email.")


def open_url(url):
    if url.startswith("snap://"):
        QDesktopServices.openUrl(QUrl(url))
    else:
        webbrowser.open(url)


class QuickCaptureDialog(QDialog):
    """Explains quick capture and, on GNOME, installs the keyboard shortcut."""

    def __init__(self, parent=None):
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtWidgets import QApplication, QKeySequenceEdit, QLineEdit

        from .. import shortcut
        from ..quick_capture import capture_command

        super().__init__(parent)
        self.setWindowTitle("Quick capture")
        self.shortcut = shortcut
        self.command = capture_command()
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        title = QLabel("Copy text from anywhere on screen")
        title.setObjectName("HeroTitle")
        intro = QLabel("Press a keyboard shortcut, select an area, and its text is copied to your clipboard. "
                       "PDF2OCR doesn't need to be open, and nothing leaves your computer.")
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        intro.setFixedWidth(460)
        layout.addWidget(title)
        layout.addWidget(intro)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setFixedWidth(460)
        if shortcut.is_gnome():
            group = QGroupBox("Keyboard shortcut")
            row = QHBoxLayout(group)
            current = shortcut.current_binding()
            self.keys = QKeySequenceEdit(QKeySequence(current or shortcut.DEFAULT_SHORTCUT))
            self.keys.setMinimumWidth(150)
            self.keys.editingFinished.connect(self._single_chord)
            self.apply_button = QPushButton("Update shortcut" if current else "Add shortcut")
            self.apply_button.setObjectName("Primary")
            self.apply_button.clicked.connect(self._install)
            self.remove_button = QPushButton("Remove")
            self.remove_button.setProperty("outlined", True)
            self.remove_button.clicked.connect(self._remove)
            self.remove_button.setVisible(bool(current))
            row.addWidget(self.keys, 1)
            row.addWidget(self.apply_button)
            row.addWidget(self.remove_button)
            layout.addWidget(group)
            if current:
                self.status.setText(f"Quick capture is set up: press <b>{current}</b> anywhere.")
        else:
            steps = QLabel("Add a custom keyboard shortcut in your desktop settings that runs the command below:<br>"
                           "• <b>KDE Plasma:</b> System Settings → Shortcuts → Add New → Command<br>"
                           "• <b>Xfce:</b> Settings → Keyboard → Application Shortcuts → Add<br>"
                           "• <b>Cinnamon / MATE:</b> Keyboard → Shortcuts → Custom Shortcuts")
            steps.setWordWrap(True)
            steps.setFixedWidth(460)
            steps.setTextFormat(Qt.RichText)
            layout.addWidget(steps)
        layout.addWidget(self.status)

        command_row = QHBoxLayout()
        command = QLineEdit(self.command)
        command.setReadOnly(True)
        command.setToolTip("Run this command (for example from a keyboard shortcut) to start a quick capture.")
        copy = QPushButton("Copy command")
        copy.setProperty("outlined", True)
        copy.clicked.connect(lambda: (QApplication.clipboard().setText(self.command),
                                      self.status.setText("Command copied.")))
        command_row.addWidget(command, 1)
        command_row.addWidget(copy)
        layout.addLayout(command_row)

        buttons = QHBoxLayout()
        try_it = QPushButton("Try it now")
        try_it.setProperty("outlined", True)
        try_it.clicked.connect(self._try)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(try_it)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _single_chord(self):
        from PyQt5.QtGui import QKeySequence
        sequence = self.keys.keySequence()
        if sequence.count() > 1:
            self.keys.setKeySequence(QKeySequence(sequence[0]))

    def _install(self):
        from PyQt5.QtGui import QKeySequence
        text = self.keys.keySequence().toString(QKeySequence.PortableText)
        if not text or "+" not in text and len(text) == 1:
            self.status.setText("Choose a shortcut with Ctrl, Alt or Super, e.g. Ctrl+Alt+O.")
            return
        try:
            self.shortcut.install(text, self.command)
        except (OSError, ValueError) as error:
            self.status.setText(f"Couldn't add the shortcut: {error}")
            return
        self.status.setText(f"Done! Press <b>{text}</b> anywhere to capture text.")
        self.apply_button.setText("Update shortcut")
        self.remove_button.show()

    def _remove(self):
        try:
            self.shortcut.remove()
        except OSError as error:
            self.status.setText(f"Couldn't remove the shortcut: {error}")
            return
        self.status.setText("Shortcut removed.")
        self.apply_button.setText("Add shortcut")
        self.remove_button.hide()

    def _try(self):
        import shlex
        import subprocess
        self.accept()
        subprocess.Popen(shlex.split(self.command), start_new_session=True)
