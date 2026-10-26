"""Saving results: plain text, Word (.docx) and searchable PDF."""

import re
import zipfile
from dataclasses import dataclass
from xml.sax.saxutils import escape

from .document import Method
from .engine import image_to_pdf_bytes
from .tools import Cancelled


@dataclass(frozen=True)
class ExportPage:
    """What an exporter needs to know about one page, captured on the UI thread."""
    title: str
    text: str
    kind: str
    source: str
    index: int
    method: Method
    text_pdf: str
    rotation: int
    crop: tuple = None
    skew: float = 0.0


def join_text(pages, separators=True):
    if separators and len(pages) > 1:
        parts = [f"--- {page.title} ---\n\n{page.text}" for page in pages]
    else:
        parts = [page.text for page in pages]
    return "\n\n".join(parts).strip() + "\n"


def export_text(pages, path, separators=True):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(join_text(pages, separators))


_INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def export_docx(pages, path):
    """A minimal Word document: one paragraph per line, a page break per page."""
    body = []
    for number, page in enumerate(pages):
        if number:
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        for line in page.text.split("\n"):
            line = escape(_INVALID_XML.sub("", line))
            body.append(f'<w:p><w:r><w:t xml:space="preserve">{line}</w:t></w:r></w:p>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + "".join(body) + '</w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/document.xml", document)


def _markdown_line(line):
    # Keep OCR text literal: neutralise characters that would start Markdown syntax.
    stripped = line.lstrip()
    if re.match(r"(#|>|[-*+]\s|\d+[.)]\s|```|---|___|\*\*\*)", stripped):
        line = line.replace(stripped, "\\" + stripped, 1)
    return line.replace("<", "&lt;")


def export_markdown(pages, path):
    parts = []
    for page in pages:
        body = "\n".join(_markdown_line(line) + ("  " if line.strip() else "") for line in page.text.split("\n"))
        parts.append(f"## {page.title}\n\n{body}" if len(pages) > 1 else body)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(parts).strip() + "\n")


_ODT_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""


def _odt_text(line):
    """Escape a line for ODF, keeping runs of spaces and tabs."""
    out = []
    for chunk in re.split(r"( {2,}|\t)", _INVALID_XML.sub("", line)):
        if chunk == "\t":
            out.append("<text:tab/>")
        elif chunk.startswith("  "):
            out.append(f'<text:s text:c="{len(chunk)}"/>')
        else:
            out.append(escape(chunk))
    return "".join(out)


def export_odt(pages, path):
    """A minimal OpenDocument text file (LibreOffice), a page break per page."""
    body = []
    for number, page in enumerate(pages):
        for index, line in enumerate(page.text.split("\n")):
            style = "PageStart" if number and index == 0 else "Standard"
            body.append(f'<text:p text:style-name="{style}">{_odt_text(line)}</text:p>')
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
               'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">'
               '<office:automatic-styles><style:style style:name="PageStart" style:family="paragraph" '
               'style:parent-style-name="Standard"><style:paragraph-properties fo:break-before="page"/>'
               '</style:style></office:automatic-styles>'
               '<office:body><office:text>' + "".join(body) + '</office:text></office:body></office:document-content>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        # The mimetype entry must come first and be stored uncompressed.
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                         compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/manifest.xml", _ODT_MANIFEST)
        archive.writestr("content.xml", content)


def export_searchable_pdf(pages, path, progress=None, token=None):
    """Original pages (or images) with tesseract's invisible text laid on top,
    so the PDF looks like the input but can be searched and copied. Slightly
    tilted pages are straightened by transforming the page content, so the
    scan isn't re-encoded and the file stays about as small as the original."""
    import io
    from pypdf import PdfReader, PdfWriter, Transformation

    writer = PdfWriter()
    readers = {}

    def reader_for(source):
        if source not in readers:
            readers[source] = PdfReader(source)
        return readers[source]

    for number, page in enumerate(pages):
        if token and token.cancelled:
            raise Cancelled()
        if page.kind == "pdf":
            target = writer.add_page(reader_for(page.source).pages[page.index])
            if page.method == Method.TEXT_LAYER:
                if progress:
                    progress(number + 1, len(pages))
                continue  # already searchable, keep it untouched
            if page.rotation:
                target.rotate(page.rotation)
        else:
            image_pdf = PdfReader(io.BytesIO(image_to_pdf_bytes(page.source, page.index, page.rotation)))
            target = writer.add_page(image_pdf.pages[0])

        if page.method == Method.OCR and page.text_pdf:
            target.transfer_rotation_to_content()
            overlay = PdfReader(page.text_pdf).pages[0]
            box = target.cropbox
            left, bottom = float(box.left), float(box.bottom)
            width, height = float(box.width), float(box.height)
            if page.skew:
                # Straighten the page the same way OCR saw it: turn its content
                # counter-clockwise about the centre (a PDF transform, no re-encoding).
                cx, cy = left + width / 2, bottom + height / 2
                target.add_transformation(Transformation().translate(-cx, -cy).rotate(page.skew).translate(cx, cy))
            if page.crop:
                # The text covers only the selected area; PDF y runs bottom-up.
                x0, y0, x1, y1 = page.crop
                left, bottom = left + x0 * width, bottom + (1 - y1) * height
                width, height = (x1 - x0) * width, (y1 - y0) * height
            sx = width / float(overlay.mediabox.width)
            sy = height / float(overlay.mediabox.height)
            target.merge_transformed_page(overlay, Transformation().scale(sx, sy).translate(left, bottom))
        if progress:
            progress(number + 1, len(pages))

    if hasattr(writer, "compress_identical_objects"):
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    with open(path, "wb") as handle:
        writer.write(handle)
