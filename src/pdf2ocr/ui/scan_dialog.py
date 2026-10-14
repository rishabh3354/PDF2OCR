"""Scanning pages straight from a scanner."""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLayout, QProgressBar,
                             QPushButton, QVBoxLayout)

from .. import scanner
from ..jobs import BackgroundCall
from .widgets import tool_button

NO_SCANNER_HELP = (
    "<b>No scanner found.</b><br><br>"
    "•&nbsp;Make sure the scanner is switched on and connected, then click refresh.<br>"
    "•&nbsp;Network scanners: most modern models work without drivers (eSCL/AirScan). "
    "Keep the scanner on the same network.<br>"
    "•&nbsp;USB scanner with the Snap version: allow USB access once by running<br>"
    "&nbsp;&nbsp;&nbsp;<code>sudo snap connect pdf2go:raw-usb</code><br>"
    "•&nbsp;Some brands need their own driver (e.g. HP: <code>hplip</code>, Epson: <i>epsonscan2</i>).")


class ScanDialog(QDialog):
    pages_scanned = pyqtSignal(list)

    def __init__(self, settings, workdir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan")
        self.setMinimumWidth(460)
        self.settings = settings
        self.folder = os.path.join(workdir, "scans")
        os.makedirs(self.folder, exist_ok=True)
        self.scanners = []
        self.options = None
        self.call = None
        self.scanned = 0

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)  # grow to fit the help text
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        title = QLabel("Scan documents")
        title.setObjectName("HeroTitle")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.device = QComboBox()
        self.device.setMinimumWidth(300)
        self.device.currentIndexChanged.connect(self._device_changed)
        self.refresh = tool_button("refresh", "Look for scanners again", size=16, outlined=True)
        self.refresh.clicked.connect(self.find_scanners)
        row.addWidget(self.device, 1)
        row.addWidget(self.refresh)
        layout.addLayout(row)

        self.form = QFormLayout()
        self.source = QComboBox()
        self.source.currentIndexChanged.connect(self._update_hint)
        self.mode = QComboBox()
        self.resolution = QComboBox()
        self.resolution.setToolTip("300 DPI is ideal for text. Use 400–600 for very small print.")
        self.form.addRow("Source", self.source)
        self.form.addRow("Color", self.mode)
        self.form.addRow("Resolution", self.resolution)
        layout.addLayout(self.form)

        self.hint = QLabel()
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.RichText)
        self.hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        footer = QHBoxLayout()
        self.count = QLabel()
        self.count.setObjectName("Muted")
        self.close_button = QPushButton("Done")
        self.close_button.setProperty("outlined", True)
        self.close_button.clicked.connect(self.close)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("Primary")
        self.scan_button.setDefault(True)
        self.scan_button.clicked.connect(self._scan_clicked)
        footer.addWidget(self.count, 1)
        footer.addWidget(self.close_button)
        footer.addWidget(self.scan_button)
        layout.addLayout(footer)

        self._set_controls_enabled(False)
        self.find_scanners()

    # ---- finding scanners -------------------------------------------------

    def _busy(self, text):
        self.hint.setText(text)
        self.progress.show()
        self.refresh.setEnabled(False)

    def _idle(self):
        self.progress.hide()
        self.call = None
        self.refresh.setEnabled(True)

    def _start(self, fn, done, failed):
        self.call = BackgroundCall(fn, self)
        self.call.finished.connect(done)
        self.call.failed.connect(failed)
        self.call.cancelled.connect(lambda: (self._idle(), self._scan_finished()))
        self.call.start()

    def find_scanners(self):
        if self.call:
            return
        self._set_controls_enabled(False)
        self.device.clear()
        self.device.addItem("Looking for scanners…")
        self._show_form(True)
        self._busy("Looking for scanners. Network scanners can take a few seconds to answer…")
        self._start(lambda _p, token: scanner.find_scanners(token), self._scanners_found, self._failed)

    def _scanners_found(self, scanners):
        self._idle()
        self.scanners = scanners
        self.device.blockSignals(True)
        self.device.clear()
        for item in scanners:
            self.device.addItem(item.label, item.device)
        self.device.blockSignals(False)
        self.device.setEnabled(bool(scanners))
        self._show_form(bool(scanners))
        if not scanners:
            self.device.addItem("No scanner found")
            self.hint.setText(NO_SCANNER_HELP)
            self.adjustSize()
            return
        last = self.settings.raw("scan/device")
        index = self.device.findData(last)
        self.device.setCurrentIndex(index if index >= 0 else 0)
        self._device_changed()

    def _show_form(self, visible):
        for field in (self.source, self.mode, self.resolution):
            for widget in (field, self.form.labelForField(field)):
                widget.setVisible(visible)

    def _device_changed(self, *_args):
        device = self.device.currentData()
        if not device or self.call:
            return
        self._set_controls_enabled(False)
        self._busy("Reading the scanner's settings…")
        self._start(lambda _p, token: scanner.scanner_options(device, token), self._options_ready, self._failed)

    def _options_ready(self, options):
        self._idle()
        self.options = options
        last_source = self.settings.raw("scan/source")
        last_mode = self.settings.raw("scan/mode")
        last_res = int(self.settings.raw("scan/resolution", 300) or 300)

        self.source.clear()
        for source in options.sources:
            self.source.addItem(source, source)
        self._pick(self.source, last_source, options.default_source)
        for widget in (self.source, self.form.labelForField(self.source)):
            widget.setVisible(bool(options.sources))

        self.mode.clear()
        for mode in options.modes:
            self.mode.addItem(scanner.mode_label(mode), mode)
        gray = next((m for m in options.modes if m.lower() in ("gray", "grey")), None)
        self._pick(self.mode, last_mode, gray or options.default_mode)

        self.resolution.clear()
        for value in options.resolutions or [300]:
            self.resolution.addItem(f"{value} DPI" + ("  ·  recommended" if value == 300 else ""), value)
        closest = min(options.resolutions or [300], key=lambda r: abs(r - last_res))
        self.resolution.setCurrentIndex(max(0, self.resolution.findData(closest)))

        for combo in (self.source, self.mode):
            combo.setEnabled(combo.count() > 0)
        self._set_controls_enabled(True)
        self._update_hint()

    @staticmethod
    def _pick(combo, *preferred):
        for value in preferred:
            index = combo.findData(value)
            if value is not None and index >= 0:
                combo.setCurrentIndex(index)
                return

    def _update_hint(self, *_args):
        if not self.options:
            return
        if scanner.is_feeder(self.source.currentData()):
            self.hint.setText("All pages in the document feeder are scanned in one go.")
        else:
            self.hint.setText("Place a page on the glass and click Scan. Repeat for each page — "
                              "every scan is added to your document and recognized automatically.")

    # ---- scanning ----------------------------------------------------------

    def _scan_clicked(self):
        if self.call:
            self.call.cancel()
            self.scan_button.setEnabled(False)
            return
        device = self.device.currentData()
        if not device:
            return
        source, mode = self.source.currentData(), self.mode.currentData()
        resolution = self.resolution.currentData() or 300
        for key, value in (("scan/device", device), ("scan/source", source), ("scan/mode", mode),
                           ("scan/resolution", resolution)):
            self.settings.set_raw(key, value)
        self.scanned += 1
        prefix = f"scan-{self.scanned:03d}-{os.urandom(2).hex()}"
        folder = self.folder
        feeder = scanner.is_feeder(source)
        self._set_controls_enabled(False)
        self.scan_button.setEnabled(True)
        self.scan_button.setText("Stop")
        self._busy("Scanning all pages in the feeder…" if feeder else "Scanning…")
        self._start(lambda _p, token: scanner.scan(device, folder, prefix, source, mode, resolution, token),
                    self._scanned, self._failed)

    def _scanned(self, paths):
        self._idle()
        self._scan_finished()
        self.pages_scanned.emit(paths)
        total = int(self.count.property("total") or 0) + len(paths)
        self.count.setProperty("total", total)
        self.count.setText(f"{total} page{'s' if total != 1 else ''} scanned")
        self.scan_button.setText("Scan next page" if not scanner.is_feeder(self.source.currentData())
                                 else "Scan again")

    def _scan_finished(self):
        self.scan_button.setText("Scan")
        self._set_controls_enabled(bool(self.options))

    def _failed(self, message):
        self._idle()
        self._scan_finished()
        self.hint.setText(f"<b>Couldn't use the scanner.</b><br>{message}")

    def _set_controls_enabled(self, enabled):
        for widget in (self.source, self.mode, self.resolution, self.scan_button, self.device):
            widget.setEnabled(enabled)

    def closeEvent(self, event):
        if self.call:
            self.call.cancel()
        super().closeEvent(event)
