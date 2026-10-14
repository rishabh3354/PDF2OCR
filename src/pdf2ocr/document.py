"""The page model and turning files on disk into pages."""

import itertools
import os
import re
from dataclasses import dataclass, field
from enum import Enum

from PIL import Image

from .tools import ToolError, run

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp",
                    ".pbm", ".pgm", ".ppm", ".pnm", ".jp2"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS

FILE_DIALOG_FILTER = ("Documents and images (" + " ".join(
    f"*{ext} *{ext.upper()}" for ext in sorted(SUPPORTED_EXTENSIONS)) + ");;"
    "PDF documents (*.pdf *.PDF);;All files (*)")

_ids = itertools.count(1)


class Status(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    WORKING = "working"
    DONE = "done"
    ERROR = "error"


class Method(Enum):
    OCR = "ocr"
    TEXT_LAYER = "text-layer"


@dataclass
class Page:
    source: str
    kind: str                    # "pdf" or "image"
    index: int                   # page number in a PDF / frame in a TIFF, 0-based
    count: int                   # number of pages in the source file
    display_name: str
    id: int = field(default_factory=lambda: next(_ids))

    status: Status = Status.PENDING
    text: str = ""
    edited: bool = False
    method: Method = None
    languages: tuple = ()
    confidence: float = None
    words: list = field(default_factory=list)     # [(word, confidence, box fractions)]
    error: str = ""

    user_rotation: int = 0       # clockwise degrees chosen by the user
    auto_rotation: int = 0       # clockwise degrees found by orientation detection
    skew: float = 0.0            # small tilt corrected before OCR (counter-clockwise degrees)
    text_pdf: str = None         # invisible text layer produced by tesseract
    force_ocr: bool = False      # ignore an existing PDF text layer
    crop: tuple = None           # only read this area (fractions of the upright page)
    derived: str = None          # flattened copy made by perspective correction
    pre_derive: tuple = None     # (user_rotation, auto_rotation) to restore on undo

    preview_path: str = None
    has_thumbnail: bool = False

    @property
    def label(self):
        if self.count > 1:
            return f"{self.display_name} · {self.index + 1}/{self.count}"
        return self.display_name

    @property
    def short_label(self):
        return f"Page {self.index + 1}" if self.count > 1 else self.display_name

    @property
    def image_source(self):
        """(kind, path, index) of the image actually shown and recognized."""
        if self.derived:
            return "image", self.derived, 0
        return self.kind, self.source, self.index

    @property
    def total_rotation(self):
        return (self.user_rotation + self.auto_rotation) % 360

    def reset_result(self):
        self.status = Status.PENDING
        self.text = ""
        self.edited = False
        self.method = None
        self.languages = ()
        self.confidence = None
        self.words = []
        self.error = ""
        self.auto_rotation = 0
        self.skew = 0.0
        self.text_pdf = None


def pdf_page_count(path):
    try:
        out = run(["pdfinfo", path], timeout=60).decode("utf-8", "replace")
    except ToolError as error:
        if "Incorrect password" in str(error):
            raise ToolError("This PDF is password protected.")
        raise ToolError(f"Could not read this PDF ({error}).")
    match = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    if not match:
        raise ToolError("Could not read the number of pages.")
    return int(match.group(1))


def image_frame_count(path):
    try:
        with Image.open(path) as img:
            # Multi-page TIFFs are scanned documents; other animated formats
            # (GIF, WebP) are treated as a single picture.
            if img.format == "TIFF":
                return max(1, getattr(img, "n_frames", 1))
            return 1
    except Exception as error:
        raise ToolError(f"Not a supported image ({error}).")


def is_supported(path):
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS


def expand_paths(paths):
    """Files are kept as given; folders contribute their supported files."""
    result = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                result += [os.path.join(root, f) for f in sorted(files) if is_supported(f)]
        else:
            result.append(path)
    return result


def load_pages(path, display_name=None):
    """Return the pages of one file. Raises ToolError with a readable message."""
    name = display_name or os.path.basename(path)
    if not os.path.isfile(path):
        raise ToolError("File not found.")
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTENSIONS or _looks_like_pdf(path):
        count = pdf_page_count(path)
        if count == 0:
            raise ToolError("This PDF has no pages.")
        return [Page(path, "pdf", i, count, name) for i in range(count)]
    count = image_frame_count(path)
    return [Page(path, "image", i, count, name) for i in range(count)]


def _looks_like_pdf(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False
