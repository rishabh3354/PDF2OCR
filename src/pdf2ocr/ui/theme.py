"""Colours, stylesheet and icons. Icons are small inline SVGs tinted to the
current theme so they stay sharp on HiDPI screens and match light/dark mode."""

import os
import subprocess
import tempfile

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import QApplication, QStyleFactory

from .icon_paint import paint_icon

LIGHT = {
    "bg": "#F4F5F7", "surface": "#FFFFFF", "surface2": "#ECEEF2", "hover": "#E4E7EC",
    "border": "#D9DDE3", "text": "#1B1F24", "muted": "#5E6876", "faint": "#98A1AE",
    "accent": "#2F5BEA", "accent_hover": "#2449C4", "accent_text": "#FFFFFF",
    "accent_soft": "#E5ECFD", "success": "#1A9455", "warning": "#B87400",
    "warning_soft": "#FFF3D6", "danger": "#CC3B3B", "viewer": "#E3E6EB",
    "selection": "#C9D7FB",
}

DARK = {
    "bg": "#15171B", "surface": "#1D2026", "surface2": "#252931", "hover": "#2D323C",
    "border": "#323843", "text": "#E7E9ED", "muted": "#A0A8B5", "faint": "#6B7381",
    "accent": "#7090FF", "accent_hover": "#8BA5FF", "accent_text": "#0D1120",
    "accent_soft": "#232C47", "success": "#3DC27E", "warning": "#E9AC3F",
    "warning_soft": "#3A3020", "danger": "#F06A6A", "viewer": "#101215",
    "selection": "#33427A",
}

_ICONS = {
    "open": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>',
    "paste": '<rect x="5" y="4.5" width="14" height="16" rx="2"/><rect x="9" y="2.5" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/>',
    "screenshot": '<path d="M4 8.5V5a1 1 0 0 1 1-1h3.5M15.5 4H19a1 1 0 0 1 1 1v3.5M20 15.5V19a1 1 0 0 1-1 1h-3.5M8.5 20H5a1 1 0 0 1-1-1v-3.5"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
    "scan": '<path d="M4 8.5V5a1 1 0 0 1 1-1h3.5M15.5 4H19a1 1 0 0 1 1 1v3.5M20 15.5V19a1 1 0 0 1-1 1h-3.5M8.5 20H5a1 1 0 0 1-1-1v-3.5M7 12h10"/>',
    "export": '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 20h14"/>',
    "settings": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><ellipse cx="12" cy="12" rx="3.8" ry="8.5"/>',
    "chevron": '<path d="M7 10l5 5 5-5"/>',
    "more": '<circle cx="12" cy="5.5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="18.5" r="1.2"/>',
    "zoom_in": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3M8.5 11h5M11 8.5v5"/>',
    "zoom_out": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3M8.5 11h5"/>',
    "fit": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
    "rotate_cw": '<path d="M19.5 12.5a7.5 7.5 0 1 1-2.6-5.7M20 4v5h-5"/>',
    "rotate_ccw": '<path d="M4.5 12.5a7.5 7.5 0 1 0 2.6-5.7M4 4v5h5"/>',
    "copy": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V5.5A1.5 1.5 0 0 0 14 4H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5h3"/>',
    "refresh": '<path d="M19.5 11A7.5 7.5 0 0 0 5.6 7.5M4.5 4v4h4M4.5 13a7.5 7.5 0 0 0 13.9 3.5M19.5 20v-4h-4"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5zM12 10v6M9 13h6"/>',
    "document": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6"/>',
    "heart": '<path d="M12 20s-7.5-4.5-7.5-10.2A4.2 4.2 0 0 1 12 7.2a4.2 4.2 0 0 1 7.5 2.6C19.5 15.5 12 20 12 20z"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.4"/>',
    "theme": '<path d="M19.5 14.5A8 8 0 1 1 9.5 4.5a6.3 6.3 0 0 0 10 10z"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    "stop": '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
    "warning": '<path d="M12 4 2.8 19.5h18.4zM12 10v4.5M12 17v.4"/>',
    "text": '<path d="M5 6h14M5 10h14M5 14h10M5 18h7"/>',
    "select_area": '<path d="M4 7.5V5a1 1 0 0 1 1-1h2.5M10.5 4h3M16.5 4H19a1 1 0 0 1 1 1v2.5M20 10.5v3M20 16.5V19a1 1 0 0 1-1 1h-2.5M13.5 20h-3M7.5 20H5a1 1 0 0 1-1-1v-2.5M4 13.5v-3M8 10h8M8 14h5"/>',
    "scanner": '<rect x="3" y="11.5" width="18" height="7.5" rx="2"/><path d="M4.5 11.5 18 5M7 15.5h5M16.5 15.5h.5"/>',
    "perspective": '<path d="M6 5h12l3 14H3z"/><path d="M9.5 9.5h5M8.5 13.5h7"/>',
    "table": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10M15 9.5v10"/>',
    "pages": '<rect x="4" y="4" width="11" height="14" rx="1.5"/><path d="M9 20.5h9.5A1.5 1.5 0 0 0 20 19V8.5"/>',
}


class Theme:
    def __init__(self):
        self.colors = dict(LIGHT)
        self.dark = False
        self._cache = {}
        self._system_dark = _detect_system_dark()

    def apply(self, mode):
        """mode is 'system', 'light' or 'dark'."""
        self.dark = self._system_dark if mode == "system" else mode == "dark"
        self.colors = dict(DARK if self.dark else LIGHT)
        self._cache.clear()
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setPalette(self._palette())
        app.setStyleSheet(self.stylesheet() + self._indicator_qss())

    def c(self, name):
        return QColor(self.colors[name])

    def _palette(self):
        c = self.c
        palette = QPalette()
        palette.setColor(QPalette.Window, c("bg"))
        palette.setColor(QPalette.WindowText, c("text"))
        palette.setColor(QPalette.Base, c("surface"))
        palette.setColor(QPalette.AlternateBase, c("surface2"))
        palette.setColor(QPalette.Text, c("text"))
        palette.setColor(QPalette.Button, c("surface"))
        palette.setColor(QPalette.ButtonText, c("text"))
        palette.setColor(QPalette.ToolTipBase, c("surface"))
        palette.setColor(QPalette.ToolTipText, c("text"))
        palette.setColor(QPalette.Highlight, c("accent"))
        palette.setColor(QPalette.HighlightedText, c("accent_text"))
        palette.setColor(QPalette.Link, c("accent"))
        palette.setColor(QPalette.PlaceholderText, c("faint"))
        palette.setColor(QPalette.Mid, c("border"))
        palette.setColor(QPalette.Midlight, c("surface2"))
        palette.setColor(QPalette.Dark, c("border"))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            palette.setColor(QPalette.Disabled, role, c("faint"))
        return palette

    def icon(self, name, color=None, size=20):
        color = color or self.colors["text"]
        key = (name, color, size)
        if key not in self._cache:
            icon = QIcon()
            icon.addPixmap(self.pixmap(name, color, size), QIcon.Normal)
            icon.addPixmap(self.pixmap(name, self.colors["faint"], size), QIcon.Disabled)
            self._cache[key] = icon
        return self._cache[key]

    def pixmap(self, name, color, size, scale=None):
        scale = scale or QApplication.instance().devicePixelRatio() or 1
        pixmap = QPixmap(int(size * scale), int(size * scale))
        pixmap.fill(Qt.transparent)
        if name not in _ICONS:
            return pixmap
        # Drawn with QPainter rather than QtSvg, which the snap's PyQt5 runtime lacks.
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_icon(painter, _ICONS[name], QColor(color), pixmap.width())
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def _indicator_qss(self):
        """Checkbox tick marks need an image file, so render one per theme."""
        folder = os.path.join(tempfile.gettempdir(), f"pdf2ocr-theme-{os.getuid()}")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"check-{'dark' if self.dark else 'light'}.png")
        self.pixmap("check", self.colors["accent_text"], 16, scale=2).save(path, "PNG")
        url = path.replace(os.sep, "/")
        return (f"QCheckBox::indicator:checked, QListView::indicator:checked {{ image: url({url}); }}\n"
                f"QListView::indicator {{ width: 16px; height: 16px; border-radius: 4px; "
                f"border: 1px solid {self.colors['border']}; background: {self.colors['surface']}; }}\n"
                f"QListView::indicator:checked {{ background: {self.colors['accent']}; "
                f"border-color: {self.colors['accent']}; }}\n")

    def stylesheet(self):
        return _QSS.format(**self.colors)


def _detect_system_dark():
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                             capture_output=True, text=True, timeout=2).stdout
        if "dark" in out:
            return True
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                             capture_output=True, text=True, timeout=2).stdout
        if "dark" in out.lower():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    # KDE and others: look at the palette Qt picked up before we restyle it.
    return QApplication.palette().color(QPalette.Window).lightness() < 128


_QSS = """
QWidget {{ font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}
QToolTip {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 5px 8px; border-radius: 6px; }}

#Header {{ background: {surface}; border-bottom: 1px solid {border}; }}
#AppTitle {{ font-size: 12pt; font-weight: 700; color: {text}; }}
#Muted, QLabel[muted="true"] {{ color: {muted}; }}
#Faint {{ color: {faint}; }}
#SectionTitle {{ font-weight: 600; color: {muted}; font-size: 9pt; letter-spacing: 0.5px; }}
#PanelTitle {{ font-weight: 600; font-size: 10.5pt; }}

QPushButton, QToolButton {{
    background: transparent; color: {text}; border: 1px solid transparent;
    border-radius: 8px; padding: 6px 10px;
}}
QPushButton:hover, QToolButton:hover {{ background: {hover}; }}
QPushButton:pressed, QToolButton:pressed, QToolButton:checked {{ background: {surface2}; border-color: {border}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {faint}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton[outlined="true"], QToolButton[outlined="true"] {{ border: 1px solid {border}; background: {surface}; }}
QPushButton[outlined="true"]:hover, QToolButton[outlined="true"]:hover {{ background: {hover}; }}
QPushButton#Primary, QToolButton#Primary {{
    background: {accent}; color: {accent_text}; font-weight: 600; padding: 7px 16px; border: none;
}}
QPushButton#Primary:hover, QToolButton#Primary:hover {{ background: {accent_hover}; }}
QPushButton#Primary:disabled {{ background: {surface2}; color: {faint}; }}
QPushButton#Danger {{ color: {danger}; border: 1px solid {border}; background: {surface}; }}
QPushButton#Link {{ color: {accent}; padding: 2px 4px; }}
QPushButton#Link:hover {{ text-decoration: underline; background: transparent; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 7px; padding: 5px 8px;
    selection-background-color: {selection}; selection-color: {text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {border}; selection-background-color: {accent_soft}; selection-color: {text}; outline: 0; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {border}; background: {surface}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}

QPlainTextEdit, QTextEdit {{
    background: {surface}; color: {text}; border: none;
    selection-background-color: {selection}; selection-color: {text};
}}
QListWidget {{ background: {bg}; border: none; outline: 0; }}
#PageList {{ background: {bg}; }}
#Card {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; }}
#Card QListWidget {{ background: transparent; }}
#Panel {{ background: {surface}; }}
#PanelHeader {{ background: {surface}; border-bottom: 1px solid {border}; }}
#ViewerToolbar {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
#Chip {{ background: {surface2}; color: {muted}; border-radius: 9px; padding: 2px 8px; font-size: 9pt; }}
#ChipAccent {{ background: {accent_soft}; color: {accent}; border-radius: 9px; padding: 2px 8px; font-size: 9pt; font-weight: 600; }}
#ChipWarning {{ background: {warning_soft}; color: {warning}; border-radius: 9px; padding: 2px 8px; font-size: 9pt; font-weight: 600; }}
#Hint {{ background: {text}; color: {surface}; border-radius: 8px; padding: 6px 12px; font-weight: 600; }}
#Banner {{ background: {accent_soft}; border-radius: 8px; }}
#DropZone {{ background: {surface}; border: 2px dashed {border}; border-radius: 16px; }}
#DropZone[active="true"] {{ border-color: {accent}; background: {accent_soft}; }}
#HeroTitle {{ font-size: 17pt; font-weight: 700; }}

QSplitter::handle {{ background: {border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QProgressBar {{ background: {surface2}; border: none; border-radius: 3px; max-height: 6px; min-width: 160px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
QStatusBar {{ background: {surface}; border-top: 1px solid {border}; color: {muted}; }}
QStatusBar::item {{ border: none; }}

QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {hover}; }}
QMenu::item:disabled {{ color: {faint}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 6px; }}
QMenu::icon {{ padding-left: 8px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {border}; border-radius: 3px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTabWidget::pane {{ border: none; }}
QGroupBox {{ border: 1px solid {border}; border-radius: 10px; margin-top: 14px; padding: 14px 12px 10px 12px; background: {surface}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {muted}; font-weight: 600; }}
QGraphicsView {{ border: none; background: {viewer}; }}
"""


_current = None


def init_theme():
    global _current
    _current = Theme()
    return _current


def theme():
    return _current
