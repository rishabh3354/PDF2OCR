"""Page image viewer with zoom, fit-to-window, rotation and area selection."""

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (QComboBox, QFrame, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
                             QGraphicsPixmapItem, QGraphicsRectItem, QPushButton,
                             QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QMenu,
                             QPlainTextEdit, QToolButton, QVBoxLayout, QWidget)

from .theme import theme
from .widgets import tool_button

MIN_SCALE, MAX_SCALE = 0.05, 8.0
MIN_SELECTION_PX = 6


class _CornerHandle(QGraphicsEllipseItem):
    """A draggable corner for perspective correction; constant size on screen."""

    RADIUS = 9

    def __init__(self, viewer):
        r = self.RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.viewer = viewer
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges
                      | QGraphicsItem.ItemIgnoresTransformations)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(20)
        pen = QPen(theme().c("surface"), 2)
        self.setPen(pen)
        self.setBrush(theme().c("accent"))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            return self.viewer._clamp(value)  # keep corners on the page
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.viewer._draw_quad()
        return super().itemChange(change, value)


class ImageViewer(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    area_selected = pyqtSignal(tuple)
    select_mode_changed = pyqtSignal(bool)
    word_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.SmoothTransformation)
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFrameShape(QFrame.NoFrame)
        self._fit = True
        self._message = ""
        self._select_mode = False
        self._origin = None
        self._band = None          # rectangle being dragged / last selection
        self._area = None          # the page's "read only this area" fractions
        self._area_items = []
        self._words = []           # box fractions per recognized word, for clicking
        self._marks = []           # boxes of uncertain words
        self._focus = []           # boxes of the words under the text cursor
        self._word_items = []
        self._press_pos = None
        self._handles = []         # perspective-correction corners
        self._quad_items = []

    # ---- image -------------------------------------------------------------

    def set_image(self, pixmap, rotation=0):
        self._message = ""
        self.clear_selection()
        self.stop_perspective()
        self._item.setPixmap(pixmap)
        self._item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
        self._item.setRotation(rotation)
        self._scene.setSceneRect(self._item.sceneBoundingRect())
        self._update_drag_mode()
        self._draw_area()
        self._draw_words()
        if self._fit:
            self.fit()
        self.viewport().update()

    def set_rotation(self, rotation):
        if not self._item.pixmap().isNull():
            self.set_image(self._item.pixmap(), rotation)

    def show_message(self, text):
        self._message = text
        self.clear_selection()
        self._item.setPixmap(QPixmap())
        self._area = None
        self._draw_area()
        self.set_words([], [])
        self._scene.setSceneRect(QRectF())
        self.setDragMode(QGraphicsView.NoDrag)
        self.viewport().update()

    def has_image(self):
        return not self._item.pixmap().isNull()

    # ---- zoom --------------------------------------------------------------

    def fit(self):
        self._fit = True
        if not self.has_image():
            return
        self.resetTransform()
        rect = self._item.sceneBoundingRect().adjusted(-16, -16, 16, 16)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.zoom_changed.emit(self.transform().m11())

    def zoom(self, factor):
        if not self.has_image():
            return
        current = self.transform().m11()
        factor = max(MIN_SCALE / current, min(MAX_SCALE / current, factor))
        self._fit = False
        self.scale(factor, factor)
        self.zoom_changed.emit(self.transform().m11())

    def wheelEvent(self, event):
        """Scrolling zooms around the cursor; drag the page to move it around.
        Shift+scroll (and touchpad sideways swipes) still scroll the page."""
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ShiftModifier or not delta or not self.has_image():
            super().wheelEvent(event)
            return
        # Proportional to the delta so touchpads zoom smoothly and a mouse
        # wheel notch (120) zooms by ~20%.
        self.zoom(1.0015 ** delta)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit:
            self.fit()

    # ---- area selection ----------------------------------------------------

    @property
    def select_mode(self):
        return self._select_mode

    def set_select_mode(self, enabled):
        if enabled == self._select_mode:
            return
        self._select_mode = enabled
        self._update_drag_mode()
        self.select_mode_changed.emit(enabled)

    def _update_drag_mode(self):
        if self._select_mode and self.has_image():
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag if self.has_image() else QGraphicsView.NoDrag)
            self.viewport().unsetCursor()

    def clear_selection(self):
        if self._band is not None:
            self._scene.removeItem(self._band)
            self._band = None
        self._origin = None

    def _clamp(self, point):
        bounds = self._item.sceneBoundingRect()
        return QPointF(min(max(point.x(), bounds.left()), bounds.right()),
                       min(max(point.y(), bounds.top()), bounds.bottom()))

    def mousePressEvent(self, event):
        selecting = self._select_mode or event.modifiers() & Qt.ShiftModifier
        if self._handles:
            super().mousePressEvent(event)  # only the corner handles react
            return
        if event.button() == Qt.LeftButton and selecting and self.has_image():
            self.clear_selection()
            self._origin = self._clamp(self.mapToScene(event.pos()))
            self._band = QGraphicsRectItem(QRectF(self._origin, self._origin))
            pen = QPen(theme().c("accent"), 2)
            pen.setCosmetic(True)
            fill = theme().c("accent")
            fill.setAlpha(40)
            self._band.setPen(pen)
            self._band.setBrush(fill)
            self._band.setZValue(10)
            self._scene.addItem(self._band)
            event.accept()
            return
        self._press_pos = event.pos() if event.button() == Qt.LeftButton else None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._origin is not None and self._band is not None:
            self._band.setRect(QRectF(self._origin, self._clamp(self.mapToScene(event.pos()))).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._origin is None:
            clicked = self._press_pos is not None and (event.pos() - self._press_pos).manhattanLength() < 4
            self._press_pos = None
            super().mouseReleaseEvent(event)
            if clicked:
                self._click_word(self.mapToScene(event.pos()))
            return
        rect = QRectF(self._origin, self._clamp(self.mapToScene(event.pos()))).normalized()
        self._band.setRect(rect)
        self._origin = None
        on_screen = self.mapFromScene(rect).boundingRect()
        if on_screen.width() < MIN_SELECTION_PX or on_screen.height() < MIN_SELECTION_PX:
            self.clear_selection()
            return
        bounds = self._item.sceneBoundingRect()
        fractions = tuple(round(min(1.0, max(0.0, value)), 5) for value in (
            (rect.left() - bounds.left()) / bounds.width(), (rect.top() - bounds.top()) / bounds.height(),
            (rect.right() - bounds.left()) / bounds.width(), (rect.bottom() - bounds.top()) / bounds.height()))
        self.area_selected.emit(fractions)
        event.accept()

    perspective_cancelled = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._handles:
            self.perspective_cancelled.emit()
            return
        if event.key() == Qt.Key_Escape and (self._select_mode or self._band is not None):
            self.clear_selection()
            self.set_select_mode(False)
            return
        super().keyPressEvent(event)

    # ---- restricted area overlay ----------------------------------------

    def set_area(self, fractions):
        self._area = fractions
        self._draw_area()

    def _draw_area(self):
        for item in self._area_items:
            self._scene.removeItem(item)
        self._area_items = []
        if not self._area or not self.has_image():
            return
        bounds = self._item.sceneBoundingRect()
        x0, y0, x1, y1 = self._area
        area = QRectF(bounds.left() + x0 * bounds.width(), bounds.top() + y0 * bounds.height(),
                      (x1 - x0) * bounds.width(), (y1 - y0) * bounds.height())
        outside = QPainterPath()
        outside.addRect(bounds)
        inner = QPainterPath()
        inner.addRect(area)
        shade = QGraphicsPathItem(outside.subtracted(inner))
        shade.setBrush(QColor(0, 0, 0, 90))
        shade.setPen(QPen(Qt.NoPen))
        border = QGraphicsRectItem(area)
        pen = QPen(theme().c("accent"), 2, Qt.DashLine)
        pen.setCosmetic(True)
        border.setPen(pen)
        for item in (shade, border):
            item.setZValue(5)
            self._scene.addItem(item)
            self._area_items.append(item)

    # ---- recognized words -------------------------------------------------

    def set_words(self, boxes, marks):
        """boxes: one fractional box (or None) per recognized word; marks: boxes to flag."""
        self._words = boxes
        self._marks = marks
        self._focus = []
        self._draw_words()

    def focus_boxes(self, boxes):
        self._focus = boxes
        self._draw_words()
        if boxes and self.has_image():
            target = self._scene_rect(boxes[0])
            for box in boxes[1:]:
                target = target.united(self._scene_rect(box))
            visible = self.mapToScene(self.viewport().rect()).boundingRect()
            if not visible.contains(target):
                self.ensureVisible(target, 60, 60)

    def _scene_rect(self, box):
        bounds = self._item.sceneBoundingRect()
        x0, y0, x1, y1 = box
        return QRectF(bounds.left() + x0 * bounds.width(), bounds.top() + y0 * bounds.height(),
                      (x1 - x0) * bounds.width(), (y1 - y0) * bounds.height())

    def _draw_words(self):
        for item in self._word_items:
            self._scene.removeItem(item)
        self._word_items = []
        if not self.has_image():
            return
        warning = theme().c("warning")
        warning.setAlpha(55)
        accent = theme().c("accent")
        accent.setAlpha(70)
        pen = QPen(theme().c("accent"), 2)
        pen.setCosmetic(True)
        for boxes, brush, outline, z in ((self._marks, warning, QPen(Qt.NoPen), 3), (self._focus, accent, pen, 6)):
            for box in boxes:
                item = QGraphicsRectItem(self._scene_rect(box).adjusted(-2, -2, 2, 2))
                item.setBrush(brush)
                item.setPen(outline)
                item.setZValue(z)
                self._scene.addItem(item)
                self._word_items.append(item)

    def _click_word(self, point):
        if not self._words or not self.has_image():
            return
        bounds = self._item.sceneBoundingRect()
        x = (point.x() - bounds.left()) / bounds.width()
        y = (point.y() - bounds.top()) / bounds.height()
        slack = 4 / max(1.0, bounds.width() * self.transform().m11())  # ~4 screen pixels
        for index, box in enumerate(self._words):
            if box and box[0] - slack <= x <= box[2] + slack and box[1] - slack <= y <= box[3] + slack:
                self.word_clicked.emit(index)
                return

    # ---- perspective correction -------------------------------------------

    @property
    def perspective_active(self):
        return bool(self._handles)

    def start_perspective(self, corners):
        """Show four draggable corners (fractions TL, TR, BR, BL)."""
        self.stop_perspective()
        if not self.has_image():
            return
        self.set_select_mode(False)
        self._handles = [_CornerHandle(self) for _ in range(4)]
        for handle in self._handles:
            self._scene.addItem(handle)
        self.set_perspective_corners(corners)
        self.setDragMode(QGraphicsView.NoDrag)

    def set_perspective_corners(self, corners):
        bounds = self._item.sceneBoundingRect()
        for handle, (x, y) in zip(self._handles, corners):
            handle.setPos(bounds.left() + x * bounds.width(), bounds.top() + y * bounds.height())
        self._draw_quad()

    def perspective_corners(self):
        bounds = self._item.sceneBoundingRect()
        return tuple(((h.pos().x() - bounds.left()) / bounds.width(), (h.pos().y() - bounds.top()) / bounds.height())
                     for h in self._handles)

    def stop_perspective(self):
        for item in self._handles + self._quad_items:
            self._scene.removeItem(item)
        was_active = bool(self._handles)
        self._handles, self._quad_items = [], []
        if was_active:
            self._update_drag_mode()

    def _draw_quad(self):
        for item in self._quad_items:
            self._scene.removeItem(item)
        self._quad_items = []
        if len(self._handles) != 4:
            return
        quad = QPainterPath()
        quad.moveTo(self._handles[0].pos())
        for handle in self._handles[1:]:
            quad.lineTo(handle.pos())
        quad.closeSubpath()
        outside = QPainterPath()
        outside.addRect(self._item.sceneBoundingRect())
        shade = QGraphicsPathItem(outside.subtracted(quad))
        shade.setBrush(QColor(0, 0, 0, 110))
        shade.setPen(QPen(Qt.NoPen))
        outline = QGraphicsPathItem(quad)
        pen = QPen(theme().c("accent"), 2)
        pen.setCosmetic(True)
        outline.setPen(pen)
        for item, z in ((shade, 15), (outline, 16)):
            item.setZValue(z)
            self._scene.addItem(item)
            self._quad_items.append(item)

    def drawForeground(self, painter, rect):
        if not self._message:
            return
        painter.save()
        painter.resetTransform()
        painter.setPen(theme().c("muted"))
        painter.drawText(self.viewport().rect(), Qt.AlignCenter | Qt.TextWordWrap, self._message)
        painter.restore()


class AreaResultCard(QFrame):
    """Floating card showing the text read from a selected area."""

    copy_clicked = pyqtSignal(str)
    copy_table_clicked = pyqtSignal()
    apply_page = pyqtSignal()
    apply_all = pyqtSignal()
    closed = pyqtSignal()
    resized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 8, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Selected area")
        title.setObjectName("PanelTitle")
        close = tool_button("close", "Close (Esc)", size=14)
        close.clicked.connect(self.close_card)
        header.addWidget(title, 1)
        header.addWidget(close)
        layout.addLayout(header)

        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.text = QPlainTextEdit()
        self.text.setFixedHeight(48)
        self.text.setStyleSheet("QPlainTextEdit { border-radius: 8px; padding: 4px; }")
        layout.addWidget(self.text)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 6, 0)
        self.copy_button = tool_button("copy", "Copy this text", text="Copy", size=16, outlined=True)
        self.copy_button.clicked.connect(lambda: self.copy_clicked.emit(self.text.toPlainText()))
        self.table_button = tool_button("table", "Copy as a table: paste into LibreOffice Calc or Excel as cells",
                                        size=16, outlined=True)
        self.table_button.clicked.connect(self.copy_table_clicked)
        self.apply_button = tool_button("select_area", "Recognize only this area instead of the whole page",
                                        text="Read only this area", size=16, outlined=True)
        self.apply_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        menu.addAction("On this page", self.apply_page)
        menu.addAction("On every page (same position)", self.apply_all)
        self.apply_button.setMenu(menu)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.table_button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
        self.hide()

    def show_busy(self):
        self.status.setText("Reading the selected area…")
        self.text.clear()
        self.text.setPlaceholderText("")
        self.text.setFixedHeight(48)
        self.copy_button.setEnabled(False)
        self.table_button.setEnabled(False)
        self.apply_button.setEnabled(True)
        self.show()
        self.raise_()

    def show_result(self, text, note):
        self.text.setPlaceholderText("No text found in this area.")
        self.text.setPlainText(text)
        self.status.setText(note)
        self._fit_text()
        self.table_button.setEnabled(bool(text))
        self.copy_button.setEnabled(bool(text))

    def _fit_text(self):
        lines = max(1, self.text.document().size().height())
        height = int(lines * self.text.fontMetrics().lineSpacing()) + 18
        self.text.setFixedHeight(max(48, min(200, height)))
        self.adjustSize()
        self.resized.emit()

    def show_error(self, message):
        self.status.setText(f"Could not read this area: {message}")
        self.copy_button.setEnabled(False)
        self.table_button.setEnabled(False)

    def close_card(self):
        self.hide()
        self.closed.emit()


class ViewerPanel(QWidget):
    """The viewer plus a floating toolbar for selection, zoom and rotation."""

    rotate_requested = pyqtSignal(int)
    perspective_requested = pyqtSignal()
    perspective_applied = pyqtSignal(tuple, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewer = ImageViewer(self)
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName("ViewerToolbar")
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(0)

        self.select_button = tool_button(
            "select_area", "Select an area to read (Ctrl+E)\nTip: Shift+drag on the page works any time",
            text="Select area", size=16)
        self.select_button.setCheckable(True)
        zoom_out = tool_button("zoom_out", "Zoom out (scroll down)", size=16)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("Muted")
        self.zoom_label.setMinimumWidth(44)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        zoom_in = tool_button("zoom_in", "Zoom in (scroll up)", size=16)
        fit = tool_button("fit", "Fit page to window", size=16)
        rotate_left = tool_button("rotate_ccw", "Rotate page left", size=16)
        rotate_right = tool_button("rotate_cw", "Rotate page right", size=16)
        self.perspective_button = tool_button("perspective", "Fix perspective: flatten a photographed page", size=16)
        bar.addWidget(self.select_button)
        bar.addSpacing(6)
        for widget in (zoom_out, self.zoom_label, zoom_in, fit):
            bar.addWidget(widget)
        bar.addSpacing(6)
        bar.addWidget(rotate_left)
        bar.addWidget(rotate_right)
        bar.addWidget(self.perspective_button)

        self.perspective_bar = QFrame(self)
        self.perspective_bar.setObjectName("ViewerToolbar")
        stack = QVBoxLayout(self.perspective_bar)
        stack.setContentsMargins(12, 8, 8, 8)
        stack.setSpacing(6)
        tip = QLabel("Drag the four corners onto the edges of the page")
        stack.addWidget(tip)
        pbar = QHBoxLayout()
        pbar.setSpacing(6)
        stack.addLayout(pbar)
        self.shape = QComboBox()
        for value, label in [("auto", "Shape: automatic"), ("a4", "A4 / A-series"), ("letter", "US Letter"),
                             ("photo", "As photographed")]:
            self.shape.addItem(label, value)
        self.shape.setToolTip("A photo can't show the paper's true proportions. “Automatic” snaps to A4 or "
                              "US Letter when the page is close to one of them.")
        cancel = QPushButton("Cancel")
        cancel.setProperty("outlined", True)
        apply = QPushButton("Straighten page")
        apply.setObjectName("Primary")
        pbar.addWidget(self.shape, 1)
        pbar.addWidget(cancel)
        pbar.addWidget(apply)
        self.perspective_bar.hide()
        cancel.clicked.connect(self.cancel_perspective)
        apply.clicked.connect(self._apply_perspective)
        self.perspective_button.clicked.connect(self.perspective_requested)
        self.viewer.perspective_cancelled.connect(self.cancel_perspective)

        self.hint = QLabel("Drag over the text you want to read  ·  Esc to stop", self)
        self.hint.setObjectName("Hint")
        self.hint.hide()
        self.card = AreaResultCard(self)

        self.select_button.toggled.connect(self.viewer.set_select_mode)
        self.viewer.select_mode_changed.connect(self._select_mode_changed)
        zoom_out.clicked.connect(lambda: self.viewer.zoom(1 / 1.25))
        zoom_in.clicked.connect(lambda: self.viewer.zoom(1.25))
        fit.clicked.connect(self.viewer.fit)
        rotate_left.clicked.connect(lambda: self.rotate_requested.emit(-90))
        rotate_right.clicked.connect(lambda: self.rotate_requested.emit(90))
        self.viewer.zoom_changed.connect(lambda s: self.zoom_label.setText(f"{round(s * 100)}%"))
        # Keep the result card next to the selection while zooming or scrolling.
        self.card.resized.connect(self.place_overlays)
        self.viewer.zoom_changed.connect(lambda _s: self.place_overlays())
        self.viewer.horizontalScrollBar().valueChanged.connect(lambda _v: self.place_overlays())
        self.viewer.verticalScrollBar().valueChanged.connect(lambda _v: self.place_overlays())

    def show_perspective(self, corners):
        self.card.hide()
        self.viewer.start_perspective(corners)
        if self.viewer.perspective_active:
            self.toolbar.hide()
            self.perspective_bar.show()
            self.place_overlays()
            self.viewer.setFocus()

    def cancel_perspective(self):
        self.viewer.stop_perspective()
        self.perspective_bar.hide()
        self.toolbar.show()

    def _apply_perspective(self):
        corners = self.viewer.perspective_corners()
        self.cancel_perspective()
        self.perspective_applied.emit(corners, self.shape.currentData())

    def _select_mode_changed(self, enabled):
        self.select_button.setChecked(enabled)
        self.hint.setVisible(enabled)
        self.place_overlays()
        if enabled:
            self.viewer.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_overlays()

    def _card_position(self):
        """Just below the selection, or above it, never covering it."""
        card, margin = self.card.size(), 10
        fallback = (max(8, self.width() - card.width() - 14), 14)
        band = self.viewer._band
        if band is None:
            return fallback
        rect = self.viewer.mapFromScene(band.rect()).boundingRect()
        x = min(max(8, rect.left()), self.width() - card.width() - 8)
        bottom_limit = self.toolbar.geometry().top() - margin
        if rect.bottom() + margin + card.height() <= bottom_limit:
            return x, rect.bottom() + margin
        if rect.top() - margin - card.height() >= 8:
            return x, rect.top() - margin - card.height()
        return fallback

    def place_overlays(self):
        self.viewer.setGeometry(self.rect())
        self.toolbar.adjustSize()
        size = self.toolbar.sizeHint()
        self.toolbar.setGeometry((self.width() - size.width()) // 2, self.height() - size.height() - 14,
                                 size.width(), size.height())
        self.hint.adjustSize()
        self.hint.move((self.width() - self.hint.width()) // 2, 14)
        self.card.adjustSize()
        self.card.move(*self._card_position())
        self.perspective_bar.adjustSize()
        self.perspective_bar.move(max(8, (self.width() - self.perspective_bar.width()) // 2), 14)
        for widget in (self.toolbar, self.hint, self.card, self.perspective_bar):
            widget.raise_()
