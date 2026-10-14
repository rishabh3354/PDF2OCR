"""User preferences, stored with QSettings (~/.config/WarlordSoft/PDF2OCR.conf)."""

import os

from PyQt5.QtCore import QSettings

from . import APP_NAME, ORG_NAME

DEFAULTS = {
    "ocr/languages": [],
    "ocr/page_layout": 3,
    "ocr/pdf_dpi": 300,
    "ocr/use_text_layer": True,
    "ocr/auto_start": True,
    "ocr/preserve_spaces": False,
    "ocr/parallel_pages": max(1, min(4, (os.cpu_count() or 2) // 2)),
    "image/auto_rotate": True,
    "image/upscale_small": True,
    "image/deskew": True,
    "image/improve_contrast": False,
    "image/black_and_white": False,
    "image/remove_noise": False,
    "results/highlight_uncertain": True,
    "results/uncertain_below": 70,
    "results/page_separators": True,
    "results/area_auto_copy": True,
    "ui/theme": "system",
    "ui/restore_session": True,
    "ui/recent": [],
    "ui/last_dir": os.path.expanduser("~"),
}


class Settings:
    def __init__(self):
        self._store = QSettings(ORG_NAME, APP_NAME)

    def get(self, key):
        default = DEFAULTS[key]
        value = self._store.value(key, default)
        if isinstance(default, bool):
            return value in (True, "true", "1", 1)
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, list):
            if value is None or value == "":
                return []
            return [value] if isinstance(value, str) else list(value)
        return value

    def set(self, key, value):
        self._store.setValue(key, value)

    def raw(self, key, default=None):
        return self._store.value(key, default)

    def set_raw(self, key, value):
        self._store.setValue(key, value)

    def ocr_options(self, store, languages):
        """The recognition settings as an OcrOptions snapshot for a worker."""
        from .engine import OcrOptions
        get = self.get
        return OcrOptions(
            languages=tuple(languages), tessdata_dir=store.tessdata_dir,
            page_layout=get("ocr/page_layout"), pdf_dpi=get("ocr/pdf_dpi"),
            use_text_layer=get("ocr/use_text_layer"), auto_rotate=get("image/auto_rotate"),
            has_osd=store.has_osd(), upscale_small=get("image/upscale_small"), deskew=get("image/deskew"),
            improve_contrast=get("image/improve_contrast"), black_and_white=get("image/black_and_white"),
            remove_noise=get("image/remove_noise"), preserve_spaces=get("ocr/preserve_spaces"),
            single_thread=get("ocr/parallel_pages") > 1)
