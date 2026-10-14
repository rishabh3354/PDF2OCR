"""Choosing OCR languages and downloading additional ones."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
                             QPushButton, QVBoxLayout, QWidget)

from ..jobs import BackgroundCall
from ..languages import HIDDEN, NAMES, display_name


def summary(codes, limit=2):
    names = [display_name(code) for code in codes]
    if not names:
        return "Choose language"
    if len(names) <= limit:
        return " + ".join(names)
    return " + ".join(names[:limit]) + f" +{len(names) - limit}"


class LanguagePicker(QFrame):
    """Popup with a searchable, checkable list of installed languages."""

    languages_changed = pyqtSignal(list)
    manage_requested = pyqtSignal()

    def __init__(self, store, selected, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground)
        self.store = store
        self.selected = list(selected)
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)
        title = QLabel("Languages in your document")
        title.setObjectName("PanelTitle")
        hint = QLabel("Select every language that appears in the text. "
                      "Choosing the right ones matters most for accuracy.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search languages…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        self.list.itemChanged.connect(self._item_changed)
        manage = QPushButton("Get more languages…")
        manage.setObjectName("Link")
        manage.setCursor(Qt.PointingHandCursor)
        manage.clicked.connect(self._manage)
        for widget in (title, hint, self.search, self.list, manage):
            layout.addWidget(widget)
        self.reload()

    def reload(self):
        self.list.blockSignals(True)
        self.list.clear()
        installed = self.store.installed()
        self.selected = [code for code in self.selected if code in installed]
        ordered = self.selected + [code for code in installed if code not in self.selected]
        for code in ordered:
            item = QListWidgetItem(f"{display_name(code)}")
            item.setToolTip(code)
            item.setData(Qt.UserRole, code)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if code in self.selected else Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._filter(self.search.text())

    def _filter(self, text):
        text = text.strip().lower()
        for row in range(self.list.count()):
            item = self.list.item(row)
            code = item.data(Qt.UserRole)
            item.setHidden(bool(text) and text not in item.text().lower() and text not in code)

    def _item_changed(self, item):
        code = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked and code not in self.selected:
            self.selected.append(code)
        elif item.checkState() == Qt.Unchecked and code in self.selected:
            if len(self.selected) == 1:
                self.list.blockSignals(True)
                item.setCheckState(Qt.Checked)  # at least one language is required
                self.list.blockSignals(False)
                return
            self.selected.remove(code)
        self.languages_changed.emit(list(self.selected))

    def _manage(self):
        self.hide()
        self.manage_requested.emit()

    def popup_below(self, widget):
        self.reload()
        self.search.clear()
        point = widget.mapToGlobal(widget.rect().bottomLeft())
        self.move(point.x(), point.y() + 4)
        self.show()
        self.search.setFocus()


class _LanguageRow(QWidget):
    def __init__(self, dialog, code):
        super().__init__()
        self.dialog = dialog
        self.code = code
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        name = QLabel(display_name(code))
        code_label = QLabel(code)
        code_label.setObjectName("Faint")
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(120)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.button = QPushButton()
        self.button.setProperty("outlined", True)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setFixedWidth(100)
        self.button.clicked.connect(self._clicked)
        layout.addWidget(name)
        layout.addWidget(code_label)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.button)
        self.call = None
        self.refresh()

    def refresh(self):
        store = self.dialog.store
        installed = self.code in self.dialog.installed
        self.progress.hide()
        self.button.setEnabled(True)
        if installed and store.is_removable(self.code):
            self.status.setText("Downloaded")
            self.button.setText("Remove")
            self.button.show()
        elif installed:
            self.status.setText("Included")
            self.button.hide()
        else:
            self.status.setText("")
            self.button.setText("Download")
            self.button.setVisible(store.can_download)

    def _clicked(self):
        if self.call:
            self.call.cancel()
            return
        if self.code in self.dialog.installed:
            self.dialog.store.remove(self.code)
            self.dialog.changed()
            return
        self.button.setText("Cancel")
        self.status.setText("")
        self.progress.setRange(0, 0)
        self.progress.show()
        store, code = self.dialog.store, self.code
        self.call = BackgroundCall(lambda progress, token: store.download(code, progress, token), self)
        self.call.progress.connect(self._progress)
        self.call.finished.connect(lambda _r: self._done(None))
        self.call.failed.connect(self._done)
        self.call.cancelled.connect(lambda: self._done(None))
        self.call.start()

    def _progress(self, received, total):
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(received)

    def _done(self, error):
        self.call = None
        self.dialog.changed()
        if error:
            self.status.setText("Failed")
            self.status.setToolTip(error)


class LanguageManager(QDialog):
    languages_installed = pyqtSignal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR languages")
        self.resize(520, 600)
        self.store = store
        self.installed = set(store.installed())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)
        title = QLabel("OCR languages")
        title.setObjectName("HeroTitle")
        if store.can_download:
            text = ("Download recognition models for more languages. Each is a one-time download "
                    "of a few MB from the official Tesseract project; recognition itself always "
                    "runs offline on your computer.")
        else:
            text = ("Additional languages can't be downloaded here because Tesseract's data folder "
                    "wasn't found. Install them with your package manager, e.g. "
                    "“sudo apt install tesseract-ocr-deu”.")
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search languages…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        for widget in (title, hint, self.search, self.list, buttons):
            layout.addWidget(widget)

        codes = set(NAMES) | self.installed
        self.rows = []
        ordered = sorted((c for c in codes if c not in HIDDEN), key=lambda c: (c not in self.installed, display_name(c)))
        for code in ordered:
            row = _LanguageRow(self, code)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.UserRole, code)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)

    def changed(self):
        self.installed = set(self.store.installed())
        for row in self.rows:
            if row.call is None:
                row.refresh()
        self.languages_installed.emit()

    def _filter(self, text):
        text = text.strip().lower()
        for row in range(self.list.count()):
            item = self.list.item(row)
            code = item.data(Qt.UserRole)
            item.setHidden(bool(text) and text not in display_name(code).lower() and text not in code)

    def reject(self):
        for row in self.rows:
            if row.call:
                row.call.cancel()
        super().reject()
