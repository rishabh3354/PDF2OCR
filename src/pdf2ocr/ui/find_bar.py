"""Find & replace bar shown above the text."""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QLineEdit, QPushButton

from .widgets import tool_button


class FindBar(QFrame):
    search_changed = pyqtSignal(str, bool)      # text, match case
    step = pyqtSignal(int)                      # +1 next, -1 previous
    replace_one = pyqtSignal(str)
    replace_all = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PanelHeader")
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 8, 10, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.find = QLineEdit()
        self.find.setPlaceholderText("Find in all pages")
        self.find.setClearButtonEnabled(True)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        self.count.setMinimumWidth(110)
        self.previous = tool_button("chevron", "Previous match (Shift+Enter)", size=14)
        self.next = tool_button("chevron", "Next match (Enter)", size=14)
        self.case = tool_button("text", "Match case", text="Aa", size=12)
        self.case.setCheckable(True)
        self.case.setToolButtonStyle(Qt.ToolButtonTextOnly)
        close = tool_button("close", "Close (Esc)", size=14)

        self.replace = QLineEdit()
        self.replace.setPlaceholderText("Replace with")
        self.replace_button = QPushButton("Replace")
        self.replace_button.setProperty("outlined", True)
        self.replace_all_button = QPushButton("Replace all")
        self.replace_all_button.setProperty("outlined", True)
        self.replace_all_button.setToolTip("Replace every match on every page (can be undone)")

        grid.addWidget(self.find, 0, 0)
        grid.addWidget(self.count, 0, 1)
        grid.addWidget(self.previous, 0, 2)
        grid.addWidget(self.next, 0, 3)
        grid.addWidget(self.case, 0, 4)
        grid.addWidget(close, 0, 5)
        grid.addWidget(self.replace, 1, 0)
        grid.addWidget(self.replace_button, 1, 1)
        grid.addWidget(self.replace_all_button, 1, 2, 1, 4)
        grid.setColumnStretch(0, 1)
        self._flip_previous_icon()

        # Searching all pages on every keystroke is wasteful; wait for a pause.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._emit_search)
        self.find.textChanged.connect(lambda _t: self._debounce.start())
        self.case.toggled.connect(lambda _c: self._emit_search())
        self.find.returnPressed.connect(self._enter)
        self.replace.returnPressed.connect(lambda: self.replace_one.emit(self.replace.text()))
        self.next.clicked.connect(lambda: self.step.emit(1))
        self.previous.clicked.connect(lambda: self.step.emit(-1))
        self.replace_button.clicked.connect(lambda: self.replace_one.emit(self.replace.text()))
        self.replace_all_button.clicked.connect(lambda: self.replace_all.emit(self.replace.text()))
        close.clicked.connect(self.close_bar)
        self.hide()

    def _flip_previous_icon(self):
        from PyQt5.QtGui import QIcon, QTransform
        pixmap = self.previous.icon().pixmap(self.previous.iconSize())
        self.previous.setIcon(QIcon(pixmap.transformed(QTransform().rotate(180))))

    def refresh_icons(self):
        self._flip_previous_icon()

    def open(self, replace_mode, text=""):
        for widget in (self.replace, self.replace_button, self.replace_all_button):
            widget.setVisible(replace_mode)
        self.show()
        if text and "\n" not in text and " " not in text:
            self.find.setText(text)
        self.find.setFocus()
        self.find.selectAll()
        self._emit_search()

    def set_replace_enabled(self, enabled):
        for widget in (self.replace, self.replace_button, self.replace_all_button):
            widget.setEnabled(enabled)

    def set_count(self, current, total, pages):
        if not self.find.text():
            self.count.setText("")
        elif total == 0:
            self.count.setText("No matches")
        else:
            where = f"  ·  {pages} page{'s' if pages != 1 else ''}" if pages > 1 else ""
            self.count.setText(f"{current} of {total}{where}")
        for button in (self.next, self.previous):
            button.setEnabled(total > 0)

    def _enter(self):
        from PyQt5.QtWidgets import QApplication
        self.step.emit(-1 if QApplication.keyboardModifiers() & Qt.ShiftModifier else 1)

    def _emit_search(self):
        self._debounce.stop()
        self.search_changed.emit(self.find.text(), self.case.isChecked())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_bar()
            return
        super().keyPressEvent(event)

    def close_bar(self):
        self.hide()
        self.closed.emit()
