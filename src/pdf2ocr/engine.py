"""The OCR pipeline. Everything here is plain Python and safe to call from
worker threads; nothing touches Qt widgets."""

import io
import os
import re
import tempfile
from dataclasses import dataclass, replace

from PIL import Image, ImageFilter, ImageOps

from .document import Method
from .tools import ToolError, run

# Pages of real text (not just a stray header) before we trust a PDF text layer.
MIN_TEXT_LAYER_CHARS = 25
SMALL_IMAGE_EDGE = 2000
MAX_UPSCALED_EDGE = 4200
PREVIEW_EDGE = 2000

PAGE_LAYOUTS = [
    (3, "Automatic"),
    (4, "Single column"),
    (6, "Single block of text"),
    (11, "Scattered text (receipts, forms)"),
    (7, "Single line"),
]


@dataclass(frozen=True)
class OcrOptions:
    languages: tuple
    tessdata_dir: str = None
    page_layout: int = 3
    pdf_dpi: int = 300
    use_text_layer: bool = True
    auto_rotate: bool = False
    has_osd: bool = False
    upscale_small: bool = True
    deskew: bool = True
    improve_contrast: bool = False
    black_and_white: bool = False
    remove_noise: bool = False
    preserve_spaces: bool = False
    single_thread: bool = False


@dataclass(frozen=True)
class PageJob:
    """An immutable snapshot of a Page, handed to a worker thread."""
    page_id: int
    kind: str
    source: str
    index: int
    user_rotation: int
    force_ocr: bool
    # Optional area to read, as fractions (x0, y0, x1, y1) of the upright page
    # as shown in the viewer, i.e. after user + auto rotation.
    crop: tuple = None
    auto_rotation: int = 0
    # Known straightening of a slightly tilted page (counter-clockwise degrees).
    # The upright page "as shown in the viewer" includes it, so area reads and
    # perspective correction apply it before cropping.
    skew: float = 0.0


@dataclass
class OcrResult:
    text: str
    method: Method
    languages: tuple = ()
    confidence: float = None
    words: list = None
    auto_rotation: int = 0
    text_pdf: str = None
    skew: float = 0.0       # degrees the image was turned (counter-clockwise) to straighten it


def _clean(text):
    text = text.replace("\f", "\n").replace("\r\n", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def extract_text_layer(pdf, index, token=None, crop=None):
    args = ["pdftotext", "-f", str(index + 1), "-l", str(index + 1), "-enc", "UTF-8"]
    if crop:
        # At -r 72 the crop box is in points, in the same rotated frame pdftoppm renders.
        width, height = pdf_page_size(pdf, index, token)
        x0, y0, x1, y1 = crop
        args += ["-r", "72", "-x", str(int(x0 * width)), "-y", str(int(y0 * height)),
                 "-W", str(int((x1 - x0) * width) + 1), "-H", str(int((y1 - y0) * height) + 1)]
    out = run(args + [pdf, "-"], token=token, timeout=120)
    return _clean(out.decode("utf-8", "replace"))


def pdf_page_size(pdf, index, token=None):
    """Displayed page size in points (width and height swap for rotated pages)."""
    out = run(["pdfinfo", "-f", str(index + 1), "-l", str(index + 1), pdf],
              token=token, timeout=60).decode("utf-8", "replace")
    size = re.search(r"^Page\s+\d+\s+size:\s+([\d.]+) x ([\d.]+)", out, re.MULTILINE)
    rot = re.search(r"^Page\s+\d+\s+rot:\s+(\d+)", out, re.MULTILINE)
    if not size:
        raise ToolError("Could not read the page size.")
    width, height = float(size.group(1)), float(size.group(2))
    if rot and int(rot.group(1)) % 180 == 90:
        width, height = height, width
    return width, height


def crop_fraction(img, crop):
    x0, y0, x1, y1 = crop
    box = (int(x0 * img.width), int(y0 * img.height), int(round(x1 * img.width)), int(round(y1 * img.height)))
    return img.crop(box)


def render_pdf_page(pdf, index, out_base, dpi=None, max_edge=None, token=None):
    args = ["pdftoppm", "-f", str(index + 1), "-l", str(index + 1), "-singlefile", "-png"]
    if max_edge:
        args += ["-scale-to", str(max_edge)]
    else:
        args += ["-r", str(dpi)]
    run(args + [pdf, out_base], token=token, timeout=300)
    return out_base + ".png"


def open_image(path, frame=0):
    """Open an image upright (honouring camera EXIF orientation) as RGB or L."""
    img = Image.open(path)
    if frame:
        img.seek(frame)
    dpi = img.info.get("dpi")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P", "PA"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.getchannel("A"))
        img = background
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img, _valid_dpi(dpi)


def _valid_dpi(dpi):
    try:
        value = int(round(float(dpi[0])))
    except (TypeError, ValueError, IndexError):
        return None
    return value if 70 <= value <= 2400 else None


def rotate_clockwise(img, degrees):
    degrees %= 360
    if not degrees:
        return img
    transpose = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}
    return img.transpose(transpose[degrees])


def _otsu_threshold(gray):
    histogram = gray.histogram()[:256]
    total = sum(histogram)
    sum_all = sum(i * h for i, h in enumerate(histogram))
    sum_bg = weight_bg = 0
    best, threshold = 0, 128
    for i, count in enumerate(histogram):
        weight_bg += count
        if not weight_bg:
            continue
        weight_fg = total - weight_bg
        if not weight_fg:
            break
        sum_bg += i * count
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between > best:
            best, threshold = between, i
    return threshold


def remove_noise(img, options):
    # Done at the original resolution: after enlarging, specks are too big for the filter.
    if options.remove_noise:
        img = img.convert("L").filter(ImageFilter.MedianFilter(3))
    return img


def enhance(img, options):
    if options.improve_contrast or options.black_and_white:
        img = img.convert("L")
    if options.improve_contrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    if options.black_and_white:
        threshold = _otsu_threshold(img)
        img = img.point(lambda value: 255 if value > threshold else 0)
    return img


def detect_skew(img, max_angle=10):
    """Small tilt of a scanned page in degrees (rotate counter-clockwise by
    this much to straighten it), or 0 when the page is straight or unclear.

    Projection profile method: when text lines are level, the row sums of
    the ink alternate sharply between text and gaps.
    """
    gray = img.convert("L")
    longest = max(gray.size)
    if longest > 1000:
        factor = 1000 / longest
        gray = gray.resize((max(1, int(gray.width * factor)), max(1, int(gray.height * factor))), Image.BILINEAR)
    threshold = _otsu_threshold(gray)
    ink = gray.point(lambda value: 255 if value < threshold else 0)
    ink_share = ink.histogram()[255] / float(ink.width * ink.height)
    if not 0.003 < ink_share < 0.4:
        return 0.0  # blank page, or a photo rather than text

    def sharpness(angle):
        rows = list(ink.rotate(angle, resample=Image.NEAREST, fillcolor=0).resize((1, ink.height), Image.BOX).getdata())
        return sum((rows[i + 1] - rows[i]) ** 2 for i in range(len(rows) - 1))

    level = sharpness(0)
    best_angle, best = 0.0, level
    for angle in range(-max_angle, max_angle + 1):
        score = sharpness(angle)
        if score > best:
            best_angle, best = float(angle), score
    for step in range(-9, 10):
        angle = best_angle + step / 10
        score = sharpness(angle)
        if score > best:
            best_angle, best = angle, score
    if abs(best_angle) < 0.3 or best < level * 1.1:
        return 0.0
    return round(best_angle, 2)


def straighten(img, angle):
    white = 255 if img.mode == "L" else (255, 255, 255)
    return img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=white)


def detect_rotation(png, options, token=None):
    """Clockwise degrees needed to make the page upright (0 if unsure)."""
    args = ["tesseract", png, "-", "--psm", "0"]
    if options.tessdata_dir:
        args += ["--tessdata-dir", options.tessdata_dir]
    try:
        out = run(args, token=token, timeout=120, env=_env(options)).decode("utf-8", "replace")
    except ToolError:
        return 0  # usually "too few characters"; leave the page as it is
    rotate = re.search(r"Rotate:\s*(\d+)", out)
    confidence = re.search(r"Orientation confidence:\s*([\d.]+)", out)
    if rotate and confidence and float(confidence.group(1)) >= 2.0:
        return int(rotate.group(1)) % 360
    return 0


def _env(options):
    env = dict(os.environ)
    if options.single_thread:
        # We already run several pages in parallel; avoid oversubscribing CPUs.
        env["OMP_THREAD_LIMIT"] = "1"
    return env


def run_tesseract(png, out_base, dpi, options, token=None):
    args = ["tesseract", png, out_base, "-l", "+".join(options.languages),
            "--psm", str(options.page_layout), "--dpi", str(dpi)]
    if options.tessdata_dir:
        args += ["--tessdata-dir", options.tessdata_dir]
    if options.preserve_spaces:
        args += ["-c", "preserve_interword_spaces=1"]
    # One pass gives us the text, per-word confidences and an invisible text
    # layer we can later lay over the original page for a searchable PDF.
    args += ["-c", "textonly_pdf=1", "txt", "tsv", "pdf"]
    run(args, token=token, timeout=600, env=_env(options))
    with open(out_base + ".txt", encoding="utf-8", errors="replace") as handle:
        text = _clean(handle.read())
    with open(out_base + ".tsv", encoding="utf-8", errors="replace") as handle:
        words = parse_tsv(handle.read())
    return text, words, out_base + ".pdf"


def parse_tsv(tsv):
    """Words as (text, confidence, (left, top, width, height) in pixels)."""
    words = []
    for line in tsv.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        word = cols[11].strip()
        try:
            confidence = float(cols[10])
            box = tuple(int(value) for value in cols[6:10])
        except ValueError:
            continue
        if word and confidence >= 0:
            words.append((word, confidence, box))
    return words


def mean_confidence(words):
    if not words:
        return None
    return sum(word[1] for word in words) / len(words)


def rotate_box(box, degrees):
    """Rotate a fractional (x0, y0, x1, y1) box clockwise with its page."""
    x0, y0, x1, y1 = box
    for _ in range((degrees % 360) // 90):
        x0, y0, x1, y1 = 1 - y1, x0, 1 - y0, x1
    return x0, y0, x1, y1


def _to_page_fractions(words, size, crop):
    """Pixel boxes in the image tesseract saw -> fractions of the upright,
    straightened page (the page as the viewer shows it)."""
    width, height = size
    cx0, cy0, cx1, cy1 = crop or (0.0, 0.0, 1.0, 1.0)
    sx, sy = (cx1 - cx0) / width, (cy1 - cy0) / height
    result = []
    for word, confidence, (left, top, w, h) in words:
        box = (cx0 + left * sx, cy0 + top * sy, cx0 + (left + w) * sx, cy0 + (top + h) * sy)
        result.append((word, confidence, tuple(round(v, 5) for v in box)))
    return result


def text_layer_words(pdf, index, rotation=0, token=None):
    """Word boxes of a digital PDF page, as fractions of the displayed page."""
    import html
    out = run(["pdftotext", "-bbox", "-f", str(index + 1), "-l", str(index + 1), pdf, "-"],
              token=token, timeout=120).decode("utf-8", "replace")
    # The <page> size in this output ignores /Rotate while the word boxes don't.
    width, height = pdf_page_size(pdf, index, token)
    words = []
    for match in re.finditer(r'<word xMin="([\d.-]+)" yMin="([\d.-]+)" xMax="([\d.-]+)" yMax="([\d.-]+)">(.*?)</word>', out):
        x0, y0, x1, y1 = (float(v) for v in match.groups()[:4])
        box = rotate_box((x0 / width, y0 / height, x1 / width, y1 / height), rotation)
        words.append((html.unescape(match.group(5)), 100.0, tuple(round(v, 5) for v in box)))
    return words


def recognize(job, options, workdir, token=None):
    """Turn one page (or an area of it) into text. Raises ToolError on failure."""
    base = os.path.join(workdir, f"page-{job.page_id}-{os.urandom(3).hex()}")
    rotation = (job.user_rotation + job.auto_rotation) % 360 if job.crop else job.user_rotation

    if job.kind == "pdf" and options.use_text_layer and not job.force_ocr:
        # A cropped text layer only lines up when we haven't rotated the page ourselves.
        if not job.crop or rotation == 0:
            text = extract_text_layer(job.source, job.index, token, job.crop)
            needed = 1 if job.crop else MIN_TEXT_LAYER_CHARS
            if sum(ch.isalnum() for ch in text) >= needed:
                words = text_layer_words(job.source, job.index, job.user_rotation, token)
                if job.crop:
                    x0, y0, x1, y1 = job.crop
                    words = [w for w in words if x0 <= (w[2][0] + w[2][2]) / 2 <= x1
                             and y0 <= (w[2][1] + w[2][3]) / 2 <= y1]
                return OcrResult(text=text, method=Method.TEXT_LAYER, words=words)

    if not options.languages:
        raise ToolError("No OCR language selected.")

    if job.kind == "pdf":
        rendered = render_pdf_page(job.source, job.index, base + "-src", dpi=options.pdf_dpi, token=token)
        img, dpi = Image.open(rendered), options.pdf_dpi
        img.load()
        os.remove(rendered)
        img = remove_noise(img.convert("RGB") if img.mode not in ("RGB", "L") else img, options)
    else:
        img, dpi = open_image(job.source, job.index)
        img = remove_noise(img, options)

    img = rotate_clockwise(img, rotation)
    if job.crop:
        if job.skew:
            img = straighten(img, job.skew)  # the area was chosen on the straightened page
        img = crop_fraction(img, job.crop)
        if min(img.size) < 4:
            return OcrResult(text="", method=Method.OCR, languages=tuple(options.languages),
                             words=[], auto_rotation=job.auto_rotation, skew=job.skew)

    if job.kind == "image" and options.upscale_small and max(img.size) < SMALL_IMAGE_EDGE:
        # Screenshots and small scans have tiny glyphs; tesseract does much
        # better once characters are at least ~20px tall.
        factor = max(1.0, min(2.0, MAX_UPSCALED_EDGE / max(img.size)))
        img = img.resize((int(img.width * factor), int(img.height * factor)), Image.LANCZOS)
        if dpi:
            dpi = int(dpi * factor)
    dpi = dpi or 300

    token and token.check()
    img = enhance(img, options)
    png = base + ".png"
    img.save(png, dpi=(dpi, dpi))

    auto_rotation = job.auto_rotation if job.crop else 0
    if options.auto_rotate and options.has_osd and not job.crop:
        auto_rotation = detect_rotation(png, options, token)
        if auto_rotation:
            img = rotate_clockwise(img, auto_rotation)
    skew = job.skew if job.crop else 0.0
    if options.deskew and not job.crop:
        token and token.check()
        skew = detect_skew(img)
        if skew:
            img = straighten(img, skew)
    if not job.crop and (auto_rotation or skew):
        img.save(png, dpi=(dpi, dpi))

    if job.crop and options.page_layout == 3:
        # An area is usually one block of text; “automatic” tends to split it apart.
        options = replace(options, page_layout=6)

    try:
        text, words, text_pdf = run_tesseract(png, base, dpi, options, token)
        words = _to_page_fractions(words, img.size, job.crop)
    finally:
        for leftover in (png, base + ".txt", base + ".tsv"):
            if os.path.exists(leftover):
                os.remove(leftover)

    return OcrResult(text=text, method=Method.OCR, languages=tuple(options.languages),
                     confidence=mean_confidence(words), words=words,
                     auto_rotation=auto_rotation, text_pdf=text_pdf, skew=skew)


def render_preview(job, out_base, edge=PREVIEW_EDGE, token=None):
    """A screen-resolution PNG of the page for the viewer and thumbnails."""
    if job.kind == "pdf":
        return render_pdf_page(job.source, job.index, out_base, max_edge=edge, token=token)
    img, _dpi = open_image(job.source, job.index)
    img.thumbnail((edge, edge), Image.LANCZOS)
    path = out_base + ".png"
    img.save(path)
    return path


def image_to_pdf_bytes(path, frame, rotation):
    """Wrap a source image in a one-page PDF (used for searchable PDF export)."""
    img, dpi = open_image(path, frame)
    img = rotate_clockwise(img, rotation)
    buffer = io.BytesIO()
    img.save(buffer, "PDF", resolution=float(dpi or 300), quality=88)
    return buffer.getvalue()


# ---- perspective correction (photographed pages) ---------------------------

def detect_page_corners(img):
    """Corners (top-left, top-right, bottom-right, bottom-left) of a sheet of
    paper photographed on a darker surface, as fractions of the image; None
    when no clear page outline is found."""
    gray = img.convert("L")
    factor = 400 / max(gray.size)
    if factor < 1:
        gray = gray.resize((max(1, int(gray.width * factor)), max(1, int(gray.height * factor))), Image.BILINEAR)
    gray = gray.filter(ImageFilter.GaussianBlur(2))
    width, height = gray.size
    threshold = _otsu_threshold(gray)
    data = gray.tobytes()
    bright = bytearray(1 if value > threshold else 0 for value in data)

    # Largest connected bright region = the paper.
    best = None
    seen = bytearray(width * height)
    for start in range(width * height):
        if not bright[start] or seen[start]:
            continue
        stack, region = [start], []
        seen[start] = 1
        while stack:
            index = stack.pop()
            region.append(index)
            x, y = index % width, index // width
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    neighbour = ny * width + nx
                    if bright[neighbour] and not seen[neighbour]:
                        seen[neighbour] = 1
                        stack.append(neighbour)
        if best is None or len(region) > len(best):
            best = region
    if not best or not 0.15 < len(best) / float(width * height) < 0.97:
        return None
    points = [(index % width, index // width) for index in best]
    corners = (min(points, key=lambda p: p[0] + p[1]), max(points, key=lambda p: p[0] - p[1]),
               max(points, key=lambda p: p[0] + p[1]), min(points, key=lambda p: p[0] - p[1]))
    return tuple(((x + 0.5) / width, (y + 0.5) / height) for x, y in corners)


def _solve(matrix, values):
    """Gaussian elimination for the small 8x8 perspective system."""
    size = len(values)
    rows = [list(row) + [value] for row, value in zip(matrix, values)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ToolError("Those corners don't form a page shape.")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(size):
            if r != col:
                ratio = rows[r][col] / rows[col][col]
                rows[r] = [a - ratio * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][size] / rows[i][i] for i in range(size)]


PAPER_SHAPES = {"a4": 1 / 2 ** 0.5, "letter": 8.5 / 11}


def page_size_for(width, height, shape="auto"):
    """Output size for a flattened page. A photo can't reveal the true
    proportions, so snap to A-series or US Letter when close (or when asked)."""
    short, long_ = min(width, height), max(width, height)
    ratio = short / long_
    if shape == "auto":
        close = [r for r in PAPER_SHAPES.values() if abs(ratio - r) / r < 0.15]
        ratio = min(close, key=lambda r: abs(ratio - r)) if close else ratio
    elif shape in PAPER_SHAPES:
        ratio = PAPER_SHAPES[shape]
    short = long_ * ratio
    return (int(short), int(long_)) if width <= height else (int(long_), int(short))


def warp_page(img, corners, shape="auto"):
    """Flatten the quadrilateral `corners` (fractions, TL/TR/BR/BL) to a rectangle."""
    import math
    quad = [(x * img.width, y * img.height) for x, y in corners]
    tl, tr, br, bl = quad
    distance = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    out_w, out_h = page_size_for(max(distance(tl, tr), distance(bl, br)),
                                 max(distance(tl, bl), distance(tr, br)), shape)
    if out_w < 50 or out_h < 50:
        raise ToolError("The selected page area is too small.")
    target = [(0, 0), (out_w, 0), (out_w, out_h), (0, out_h)]
    matrix, values = [], []
    for (x, y), (u, v) in zip(target, quad):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        values.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        values.append(v)
    coefficients = _solve(matrix, values)
    return img.transform((out_w, out_h), Image.PERSPECTIVE, coefficients, Image.BICUBIC)


def load_upright(job, dpi, token=None):
    """The full-resolution page image as the viewer shows it (rotations applied)."""
    base = os.path.join(tempfile.gettempdir(), f"pdf2ocr-upright-{os.getpid()}-{job.page_id}")
    if job.kind == "pdf":
        rendered = render_pdf_page(job.source, job.index, base, dpi=dpi, token=token)
        img = Image.open(rendered)
        img.load()
        os.remove(rendered)
        img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    else:
        img, found = open_image(job.source, job.index)
        dpi = found or 300
    img = rotate_clockwise(img, job.user_rotation + job.auto_rotation)
    return (straighten(img, job.skew) if job.skew else img), dpi


def straighten_photo(job, corners, out_path, dpi, shape="auto", token=None):
    img, dpi = load_upright(job, dpi, token)
    token and token.check()
    warp_page(img, corners, shape).save(out_path, dpi=(dpi, dpi))
    return out_path
