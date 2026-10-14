"""Sidebar with page thumbnails and their recognition status."""

from PyQt5.QtCore import QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPainterPath, QPen, QTransform
from PyQt5.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

from ..document import Method, Status
from .theme import theme

CARD_HEIGHT = 196
THUMB_HEIGHT = 150
PAGE_ID_ROLE = Qt.UserRole


class PageDelegate(QStyledItemDelegate):
    def __init__(self, page_list):
        super().__init__(page_list)
        self.page_list = page_list

    def sizeHint(self, option, index):
        return QSize(option.rect.width() or 180, CARD_HEIGHT)

    def paint(self, painter, option, index):
        page = self.page_list.page_for(index.data(PAGE_ID_ROLE))
        if page is None:
            return
        c = theme().c
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(option.rect.adjusted(8, 4, -8, -4))
        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver
        if selected or hovered:
            painter.setPen(QPen(c("accent"), 1.5) if selected else Qt.NoPen)
            painter.setBrush(c("accent_soft") if selected else c("hover"))
            painter.drawRoundedRect(card, 10, 10)

        thumb_area = QRect(int(card.left()) + 10, int(card.top()) + 8, int(card.width()) - 20, THUMB_HEIGHT)
        pixmap = self.page_list.thumbnails.get(page.id)
        if pixmap is not None and not pixmap.isNull():
            if page.total_rotation:
                pixmap = pixmap.transformed(QTransform().rotate(page.total_rotation), Qt.SmoothTransformation)
            scaled = pixmap.size().scaled(thumb_area.size(), Qt.KeepAspectRatio)
            target = QRect(0, 0, scaled.width(), scaled.height())
            target.moveCenter(thumb_area.center())
            painter.setPen(QPen(c("border"), 1))
            painter.drawRect(target.adjusted(-1, -1, 0, 0))
            painter.drawPixmap(target, pixmap)
        else:
            target = QRect(0, 0, int(THUMB_HEIGHT * 0.72), THUMB_HEIGHT)
            target.moveCenter(thumb_area.center())
            painter.setPen(QPen(c("border"), 1))
            painter.setBrush(c("surface"))
            painter.drawRect(target)

        self._paint_badge(painter, page, target)

        text_rect = QRect(int(card.left()) + 8, thumb_area.bottom() + 6, int(card.width()) - 16, 20)
        painter.setPen(c("text") if selected else c("muted"))
        metrics = painter.fontMetrics()
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                         metrics.elidedText(page.label, Qt.ElideMiddle, text_rect.width()))
        painter.restore()

    def _paint_badge(self, painter, page, target):
        c = theme().c
        threshold = self.page_list.uncertain_below
        if page.status == Status.DONE:
            low = page.method == Method.OCR and (page.confidence is None or page.confidence < threshold)
            color, icon = (c("warning"), "warning") if low else (c("success"), "check")
        elif page.status == Status.ERROR:
            color, icon = c("danger"), "close"
        elif page.status == Status.WORKING:
            color, icon = c("accent"), "refresh"
        elif page.status == Status.QUEUED:
            color, icon = c("faint"), "more"
        else:
            return
        size = 22
        badge = QRectF(target.right() - size + 6, target.top() - 6, size, size)
        path = QPainterPath()
        path.addEllipse(badge)
        painter.setPen(QPen(c("surface"), 2))
        painter.setBrush(color)
        painter.drawPath(path)
        glyph = theme().pixmap(icon, theme().colors["surface"], 14)
        painter.drawPixmap(badge.adjusted(4, 4, -4, -4).toRect(), glyph)


class PageList(QListWidget):
    """Order of items here is the order pages are exported in."""

    current_page_changed = pyqtSignal(object)
    context_menu_requested = pyqtSignal(object)
    order_changed = pyqtSignal()

    def __init__(self, pages, parent=None):
        super().__init__(parent)
        self.setObjectName("PageList")
        self.pages = pages              # shared dict: page id -> Page
        self.thumbnails = {}            # page id -> QPixmap
        self.uncertain_below = 70
        self.setItemDelegate(PageDelegate(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.context_menu_requested.emit(self.mapToGlobal(pos)))
        self.currentItemChanged.connect(self._current_changed)
        self.model().rowsMoved.connect(lambda *args: self.order_changed.emit())

    def page_for(self, page_id):
        return self.pages.get(page_id)

    def add_pages(self, pages):
        for page in pages:
            item = QListWidgetItem()
            item.setData(PAGE_ID_ROLE, page.id)
            item.setToolTip(page.label)
            self.addItem(item)

    def ordered_ids(self):
        return [self.item(row).data(PAGE_ID_ROLE) for row in range(self.count())]

    def selected_ids(self):
        rows = sorted(self.row(item) for item in self.selectedItems())
        return [self.item(row).data(PAGE_ID_ROLE) for row in rows]

    def current_id(self):
        item = self.currentItem()
        return item.data(PAGE_ID_ROLE) if item else None

    def select_id(self, page_id):
        row = self._row_of(page_id)
        if row is not None:
            self.setCurrentRow(row)

    def remove_ids(self, ids):
        for page_id in ids:
            row = self._row_of(page_id)
            if row is not None:
                self.takeItem(row)
            self.thumbnails.pop(page_id, None)

    def refresh_page(self, page_id):
        row = self._row_of(page_id)
        if row is not None:
            self.update(self.model().index(row, 0))

    def step(self, delta):
        if self.count():
            self.setCurrentRow(max(0, min(self.count() - 1, self.currentRow() + delta)))

    def _row_of(self, page_id):
        for row in range(self.count()):
            if self.item(row).data(PAGE_ID_ROLE) == page_id:
                return row
        return None

    def _current_changed(self, current, _previous):
        self.current_page_changed.emit(current.data(PAGE_ID_ROLE) if current else None)
