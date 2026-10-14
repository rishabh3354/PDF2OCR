"""Rebuilding tables from recognized word positions, and saving them as
CSV, tab-separated text (for pasting into spreadsheets) or Excel (.xlsx)."""

import csv
import re
import zipfile
from xml.sax.saxutils import escape

BINS = 1000


def _median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else 0.0


def build_table(words):
    """words: [(text, confidence, (x0, y0, x1, y1))] as page fractions.
    Returns rows of cell strings ([] when there is nothing to build)."""
    items = [(text, box) for text, _conf, box in words
             if text.strip() and box and box[2] > box[0] and box[3] > box[1]]
    if not items:
        return []
    line_height = _median([box[3] - box[1] for _t, box in items])
    char_width = _median([(box[2] - box[0]) / max(1, len(text)) for text, box in items])

    # 1. Rows: words whose vertical centres are close belong to the same line.
    rows = []
    for text, box in sorted(items, key=lambda item: (item[1][1] + item[1][3]) / 2):
        centre = (box[1] + box[3]) / 2
        if rows and abs(centre - rows[-1]["centre"]) < line_height * 0.6:
            row = rows[-1]
            row["words"].append((text, box))
            row["centre"] += (centre - row["centre"]) / len(row["words"])
        else:
            rows.append({"centre": centre, "words": [(text, box)]})

    # 2. Cells: split a line where the gap is much wider than this document's
    #    normal word space (measured, since table layouts are often tight).
    spaces = []
    for row in rows:
        ordered = sorted(row["words"], key=lambda item: item[1][0])
        spaces += [b[0] - a[2] for (_ta, a), (_tb, b) in zip(ordered, ordered[1:]) if b[0] > a[2]]
    # Word spaces are narrower than a character or so; column gaps are wider.
    word_spaces = [space for space in spaces if space < char_width * 1.5]
    typical_space = _median(word_spaces) if word_spaces else char_width * 0.5
    gap = max(char_width * 1.0, typical_space * 2.5)
    lines = []
    for row in rows:
        cells = []
        for text, box in sorted(row["words"], key=lambda item: item[1][0]):
            if cells and box[0] - cells[-1][2] <= gap:
                cells[-1] = (cells[-1][0] + " " + text, cells[-1][1], box[2])
            else:
                cells.append((text, box[0], box[2]))
        lines.append(cells)

    # 3. Columns: x ranges that stay empty in (almost) every multi-cell row
    #    separate the columns, even if one long cell pokes into a gap.
    multi = [cells for cells in lines if len(cells) > 1]
    if not multi:
        return [[cells[0][0]] for cells in lines]
    left = min(cell[1] for cells in lines for cell in cells)
    right = max(cell[2] for cells in lines for cell in cells)
    span = max(right - left, 1e-9)
    to_bin = lambda x: min(BINS - 1, max(0, int((x - left) / span * BINS)))
    coverage = [0] * BINS
    for cells in multi:
        for _text, x0, x1 in cells:
            for b in range(to_bin(x0), to_bin(x1) + 1):
                coverage[b] += 1
    allowed = len(multi) // 4  # a single wide header cell mustn't merge the columns
    columns, start = [], None
    for b, count in enumerate(coverage + [0]):
        if count > allowed and start is None:
            start = b
        elif count <= allowed and start is not None:
            columns.append((start, b - 1))
            start = None
    # A gap that some row crosses only separates columns if it is at least a
    # word-space wide (left-aligned headers over right-aligned numbers leave
    # slivers like that); a gap no row crosses always does.
    gap_bins = gap / span * BINS
    merged = columns[:1]
    for a, b in columns[1:]:
        between = coverage[merged[-1][1] + 1:a]
        if between and min(between) > 0 and len(between) < gap_bins:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    columns = merged
    if not columns:
        return [[" ".join(cell[0] for cell in cells)] for cells in lines]

    def column_of(x0, x1):
        centre = to_bin((x0 + x1) / 2)
        for index, (a, b) in enumerate(columns):
            if a <= centre <= b:
                return index
        return min(range(len(columns)), key=lambda i: min(abs(centre - columns[i][0]), abs(centre - columns[i][1])))

    table = []
    for cells in lines:
        row = [""] * len(columns)
        for text, x0, x1 in cells:
            index = column_of(x0, x1)
            row[index] = (row[index] + " " + text).strip()
        table.append(row)
    return table


def is_table(rows):
    """At least two rows that use two or more columns."""
    return sum(1 for row in rows if sum(1 for cell in row if cell) >= 2) >= 2


def describe(rows):
    columns = max((len(row) for row in rows), default=0)
    return f"{len(rows)} row{'s' if len(rows) != 1 else ''} × {columns} column{'s' if columns != 1 else ''}"


def to_tsv(rows):
    clean = lambda cell: re.sub(r"[\t\r\n]+", " ", cell)
    return "\n".join("\t".join(clean(cell) for cell in row) for row in rows) + "\n"


def export_csv(rows, path):
    # utf-8-sig so Excel recognizes the encoding; LibreOffice handles both.
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)


_NUMBER = re.compile(r"^[-+]?(\d+|\d{1,3}(,\d{3})+)(\.\d+)?$")
_INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _cell_xml(reference, value):
    """Plain numbers become real numbers (so sums work); everything else text."""
    if _NUMBER.match(value) and not (len(value) > 1 and value.startswith("0") and value[1].isdigit()):
        return f'<c r="{reference}"><v>{value.replace(",", "")}</v></c>'
    text = escape(_INVALID_XML.sub("", value))
    return f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _column_name(index):
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_name(name, used):
    name = re.sub(r"[\[\]:*?/\\]", " ", name).strip()[:31] or "Sheet"
    base, number = name, 2
    while name.lower() in used:
        suffix = f" ({number})"
        name, number = base[:31 - len(suffix)] + suffix, number + 1
    used.add(name.lower())
    return name


def export_xlsx(sheets, path):
    """sheets: [(name, rows)]. A minimal but valid Excel workbook."""
    used = set()
    names = [_sheet_name(name, used) for name, _rows in sheets]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1))
        archive.writestr("[Content_Types].xml",
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/xl/workbook.xml" '
                         'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         + overrides + '</Types>')
        archive.writestr("_rels/.rels",
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                         'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml",
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                         + "".join(f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                                   for i, name in enumerate(names, 1))
                         + '</sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels",
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
                                   f'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                                   for i in range(1, len(sheets) + 1))
                         + '</Relationships>')
        for i, (_name, rows) in enumerate(sheets, 1):
            body = []
            for r, row in enumerate(rows, 1):
                cells = "".join(_cell_xml(f"{_column_name(c)}{r}", value) for c, value in enumerate(row) if value)
                body.append(f'<row r="{r}">{cells}</row>')
            archive.writestr(f"xl/worksheets/sheet{i}.xml",
                             '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                             '<sheetData>' + "".join(body) + '</sheetData></worksheet>')
