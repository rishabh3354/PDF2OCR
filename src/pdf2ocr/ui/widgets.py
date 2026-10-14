"""Small reusable widgets."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton

from .theme import theme


def tool_button(icon, tooltip, text=None, size=18, outlined=False, parent=None):
    button = QToolButton(parent)
    button.setIcon(theme().icon(icon, size=size))
    button.setIconSize(QSize(size, size))
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setProperty("iconName", icon)
    if text:
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    if outlined:
        button.setProperty("outlined", True)
    return button


def refresh_icons(root):
    """Re-tint every icon button below root after the theme changed."""
    for button in root.findChildren((QToolButton, QPushButton)):
        name = button.property("iconName")
        if name:
            color = theme().colors["accent_text"] if button.objectName() == "Primary" else None
            button.setIcon(theme().icon(name, color=color, size=button.iconSize().width()))


def chip(text="", style="Chip"):
    label = QLabel(text)
    label.setObjectName(style)
    return label


def set_chip_style(label, style):
    if label.objectName() != style:
        label.setObjectName(style)
        label.style().unpolish(label)
        label.style().polish(label)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Banner(QFrame):
    """A slim notice bar with an optional action button."""

    action_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        self.icon = QLabel()
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.action = QPushButton()
        self.action.setProperty("outlined", True)
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.clicked.connect(self.action_clicked)
        close = tool_button("close", "Dismiss", size=14)
        close.clicked.connect(self.hide)
        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.action)
        layout.addWidget(close)
        self.hide()

    def show_message(self, text, action=None, icon="info"):
        self.icon.setPixmap(theme().pixmap(icon, theme().colors["accent"], 18))
        self.text.setText(text)
        self.action.setVisible(bool(action))
        self.action.setText(action or "")
        self.show()

