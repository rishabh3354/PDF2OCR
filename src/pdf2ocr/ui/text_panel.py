"""Recognized text for the current page (editable) or all pages (read-only)."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                             QPlainTextEdit, QTextEdit, QVBoxLayout)

from ..document import Method, Status
from ..languages import display_name
from .theme import theme
from .find_bar import FindBar
from .widgets import chip, set_chip_style, tool_button


NO_TEXT_TIPS = ("No text was found on this page.\n\n"
                "Things that usually help:\n"
                "•  Make sure the right language is selected (top bar)\n"
                "•  Settings → Image cleanup → “Remove specks and noise” or “Improve contrast”\n"
                "•  Settings → Scan resolution 400 DPI for small print\n"
                "•  Settings → Page layout “Scattered text” for receipts and forms")


def locate_words(text, words):
    """Find each recognized word (in reading order) inside the plain text.
    Returns [(start, end, word_index)]; words that can't be found are skipped."""
    found_words, position = [], 0
    for index, (word, _confidence, _box) in enumerate(words):
        found = text.find(word, position)
        if found < 0 or found - position > 200:
            continue
        found_words.append((found, found + len(word), index))
        position = found + len(word)
    return found_words


class TextPanel(QFrame):
    text_edited = pyqtSignal(int, str)
    rerun_requested = pyqtSignal(int, bool)
    area_reset_requested = pyqtSignal(int)
    words_focused = pyqtSignal(list)   # boxes of the words under the cursor / selection
    mode_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.page = None
        self.all_pages_text = None
        self.highlight = True
        self.threshold = 70
        self._loading = False
        self._links = []                   # [(QTextCursor spanning a word, word index)]
        self._uncertain_selections = []
        self._search_selections = []

        header = QFrame()
        header.setObjectName("PanelHeader")
        top = QVBoxLayout(header)
        top.setContentsMargins(14, 10, 10, 10)
        top.setSpacing(6)

        row = QHBoxLayout()
        self.title = QLabel("Text")
        self.title.setObjectName("PanelTitle")
        row.addWidget(self.title, 1)

        self.page_mode = tool_button("text", "Show the text of this page", text="Page", size=14)
        self.all_mode = tool_button("pages", "Show the text of all pages together", text="All pages", size=14)
        group = QButtonGroup(self)
        for button in (self.page_mode, self.all_mode):
            button.setCheckable(True)
            group.addButton(button)
            row.addWidget(button)
        self.page_mode.setChecked(True)
        group.buttonToggled.connect(self._mode_toggled)

        self.copy_button = tool_button("copy", "Copy text to clipboard", size=16)
        self.copy_button.clicked.connect(self.copy)
        self.rerun_button = tool_button("refresh", "Recognize this page again", size=16)
        self.rerun_button.clicked.connect(self._rerun)
        row.addSpacing(6)
        row.addWidget(self.copy_button)
        row.addWidget(self.rerun_button)
        top.addLayout(row)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.method_chip = chip()
        self.confidence_chip = chip()
        self.uncertain_chip = chip(style="ChipWarning")
        self.area_chip = tool_button("close", "Only the selected area of this page is read.\n"
                                              "Click to read the whole page again.",
                                     text="Selected area only", size=12)
        self.area_chip.setObjectName("ChipAccent")
        self.area_chip.setLayoutDirection(Qt.RightToLeft)
        self.area_chip.clicked.connect(lambda: self.page and self.area_reset_requested.emit(self.page.id))
        for widget in (self.method_chip, self.confidence_chip, self.uncertain_chip, self.area_chip):
            chips.addWidget(widget)
        chips.addStretch(1)
        top.addLayout(chips)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("TextEditor")
        font = QFont(self.editor.font())
        font.setPointSizeF(font.pointSizeF() + 1.5)
        self.editor.setFont(font)
        self.editor.document().setDocumentMargin(14)
        self.editor.textChanged.connect(self._text_changed)
        self.editor.cursorPositionChanged.connect(self._cursor_moved)

        self.footer = QLabel()
        self.footer.setObjectName("Faint")
        self.footer.setContentsMargins(14, 6, 14, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.find_bar = FindBar()
        layout.addWidget(header)
        layout.addWidget(self.find_bar)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.footer)
        self.show_page(None)

    @property
    def showing_all(self):
        return self.all_mode.isChecked()

    # ---- content -----------------------------------------------------------

    def show_page(self, page):
        self.page = page
        if self.showing_all:
            return
        self._loading = True
        self._uncertain_selections, self._search_selections = [], []
        self.editor.setExtraSelections([])
        self._links = []
        for widget in (self.method_chip, self.confidence_chip, self.uncertain_chip, self.area_chip):
            widget.hide()
        self.copy_button.setEnabled(False)
        self.rerun_button.setEnabled(page is not None and page.status in (Status.DONE, Status.ERROR))

        if page is None:
            self.title.setText("Text")
            self._set_text("", "Open a document to see its text here.", read_only=True)
        else:
            self.title.setText(page.label)
            if page.status == Status.DONE:
                self._set_text(page.text, NO_TEXT_TIPS, read_only=False)
                self.copy_button.setEnabled(bool(page.text))
                self._build_links(page)
                self._show_result_chips(page)
            elif page.status == Status.WORKING:
                self._set_text("", "Recognizing this page…", read_only=True)
            elif page.status == Status.QUEUED:
                self._set_text("", "Waiting in line to be recognized…", read_only=True)
            elif page.status == Status.ERROR:
                self._set_text("", f"Could not recognize this page.\n\n{page.error}", read_only=True)
            else:
                self._set_text("", "Not recognized yet. Click “Recognize” to extract the text.", read_only=True)
        self._update_footer()
        self._loading = False
        self.words_focused.emit([])

    def show_all(self, text):
        self.all_pages_text = text
        if not self.showing_all:
            return
        self._loading = True
        self.title.setText("All pages")
        self._uncertain_selections, self._search_selections = [], []
        self.editor.setExtraSelections([])
        self._links = []
        for widget in (self.method_chip, self.confidence_chip, self.uncertain_chip, self.area_chip):
            widget.hide()
        self._set_text(text, "Nothing recognized yet.", read_only=True)
        self.copy_button.setEnabled(bool(text.strip()))
        self.rerun_button.setEnabled(False)
        self._update_footer()
        self._loading = False

    def _set_text(self, text, placeholder, read_only):
        # Qt 5 only re-evaluates placeholder visibility when the text changes,
        # so set the placeholder first and always reset an empty document.
        self.editor.setPlaceholderText(placeholder)
        if not text or self.editor.toPlainText() != text:
            self.editor.setPlainText(text)
        self.editor.setReadOnly(read_only)

    def _show_result_chips(self, page):
        self.area_chip.setVisible(bool(page.crop))
        if page.method == Method.TEXT_LAYER:
            self.method_chip.setText("Text from PDF · exact")
            self.method_chip.setToolTip("This page already contained real text, so it was copied "
                                        "exactly instead of using OCR. Use “Recognize again” to force OCR.")
            self.method_chip.show()
            return
        languages = " + ".join(display_name(code) for code in page.languages)
        self.method_chip.setText(f"OCR · {languages}")
        self.method_chip.setToolTip("Recognized locally with Tesseract OCR.")
        self.method_chip.show()
        if page.confidence is not None:
            confidence = round(page.confidence)
            low = confidence < self.threshold
            set_chip_style(self.confidence_chip, "ChipWarning" if low else "ChipAccent")
            self.confidence_chip.setText(f"{confidence}% confidence")
            self.confidence_chip.setToolTip("Average certainty of the recognized words. Low values usually mean "
                                            "a blurry scan or the wrong language selected.")
            self.confidence_chip.show()
        if self.highlight and not page.edited:
            self._highlight_uncertain(page)

    def _build_links(self, page):
        if page.edited:
            return  # recognized positions no longer match the edited text
        for start, end, index in locate_words(page.text, page.words):
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            self._links.append((cursor, index))

    def _highlight_uncertain(self, page):
        ranges = [(cursor.selectionStart(), cursor.selectionEnd()) for cursor, index in self._links
                  if page.words[index][1] < self.threshold]
        if not ranges:
            return
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        fmt.setUnderlineColor(theme().c("warning"))
        background = theme().c("warning")
        background.setAlpha(40)
        fmt.setBackground(background)
        selections = []
        for start, end in ranges:
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)
        self._uncertain_selections = selections
        self._apply_selections()
        count = len(ranges)
        self.uncertain_chip.setText(f"{count} word{'s' if count != 1 else ''} to check")
        self.uncertain_chip.setToolTip("Underlined words were hard to read. Compare them with the page image.")
        self.uncertain_chip.show()

    # ---- interaction -------------------------------------------------------

    def _text_changed(self):
        self._update_footer()
        if self._loading or self.showing_all or self.page is None or self.page.status != Status.DONE:
            return
        if not self.page.edited:
            self._uncertain_selections = []
            self._apply_selections()
            self.uncertain_chip.hide()
        self.text_edited.emit(self.page.id, self.editor.toPlainText())

    def _apply_selections(self):
        self.editor.setExtraSelections(self._uncertain_selections + self._search_selections)

    def set_search_highlights(self, ranges, current=None):
        """Mark every match in the visible text and select the current one."""
        match_format = QTextCharFormat()
        color = theme().c("warning")
        color.setAlpha(90)
        match_format.setBackground(color)
        current_format = QTextCharFormat()
        current_format.setBackground(theme().c("accent"))
        current_format.setForeground(theme().c("accent_text"))
        selections = []
        for start, end in ranges:
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection.cursor = cursor
            selection.format = current_format if (start, end) == current else match_format
            selections.append(selection)
        self._search_selections = selections
        self._apply_selections()
        if current:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(current[0])
            cursor.setPosition(current[1], QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

    def replace_range(self, start, end, replacement):
        """Replace through the editor so undo (Ctrl+Z) and word links keep working."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(replacement)

    def _cursor_moved(self):
        if self._loading or not self._links or self.page is None:
            return
        cursor = self.editor.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        boxes = []
        for link, index in self._links:
            if not link.hasSelection():
                continue  # the word was deleted while editing
            if link.selectionStart() <= end and link.selectionEnd() >= start:
                boxes.append(self.page.words[index][2])
            elif link.selectionStart() > end:
                break
        self.words_focused.emit(boxes)

    def select_word(self, index):
        """Put the text cursor on a word (when it was clicked on the page image)."""
        for link, link_index in self._links:
            if link_index == index and link.hasSelection():
                self.editor.setTextCursor(QTextCursor(link))
                self.editor.ensureCursorVisible()
                self.editor.setFocus()
                return True
        return False

    def _update_footer(self):
        text = self.editor.toPlainText()
        if not text:
            self.footer.setText(" ")
            return
        words = len(text.split())
        edited = "  ·  edited" if (self.page and self.page.edited and not self.showing_all) else ""
        self.footer.setText(f"{words:,} words  ·  {len(text):,} characters{edited}")

    def _mode_toggled(self, _button, _checked):
        if not _checked:
            return
        self.mode_changed.emit(self.showing_all)
        if self.showing_all:
            self.show_all(self.all_pages_text or "")
        else:
            self.show_page(self.page)

    def _rerun(self):
        if self.page is not None:
            self.rerun_requested.emit(self.page.id, self.page.method == Method.TEXT_LAYER)

    def copy(self):
        text = self.editor.textCursor().selectedText().replace(" ", "\n") or self.editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.window().statusBar().showMessage("Text copied to clipboard", 3000)
