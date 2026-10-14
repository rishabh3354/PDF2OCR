"""Draws the app's line icons with QPainter.

The icons are written in a small subset of SVG (path, rect, circle, ellipse,
stroke only). Drawing them ourselves avoids depending on the QtSvg module,
which some PyQt5 runtimes - including the one the snap uses - don't ship.
"""

import math
import re
import xml.etree.ElementTree as ElementTree

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainterPath

_TOKEN = re.compile(r"[MmLlHhVvCcSsQqAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}


def _arc(path, x1, y1, rx, ry, large, sweep, x2, y2):
    """SVG elliptical arc (no x-axis rotation) as a QPainterPath arc."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        path.lineTo(x2, y2)
        return
    rx, ry = abs(rx), abs(ry)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    scale = dx * dx / (rx * rx) + dy * dy / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    numerator = rx * rx * ry * ry - rx * rx * dy * dy - ry * ry * dx * dx
    denominator = rx * rx * dy * dy + ry * ry * dx * dx
    factor = math.sqrt(max(0.0, numerator / denominator)) * (-1 if large == sweep else 1)
    cx = factor * rx * dy / ry + (x1 + x2) / 2
    cy = -factor * ry * dx / rx + (y1 + y2) / 2
    start = math.atan2((y1 - cy) / ry, (x1 - cx) / rx)
    end = math.atan2((y2 - cy) / ry, (x2 - cx) / rx)
    delta = end - start
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    # Qt measures angles counter-clockwise on screen; SVG's y axis points down.
    path.arcTo(QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry), -math.degrees(start), -math.degrees(delta))


def path_from_svg(d):
    tokens = _TOKEN.findall(d)
    path = QPainterPath()
    x = y = start_x = start_y = 0.0
    last_control = None
    command = None
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command in "Zz":
                path.closeSubpath()
                x, y = start_x, start_y
                last_control = None
                continue
        count = _ARGS[command.upper()]
        values = [float(v) for v in tokens[i:i + count]]
        i += count
        relative = command.islower()
        upper = command.upper()
        ox, oy = (x, y) if relative else (0.0, 0.0)
        control = None
        if upper == "M":
            x, y = ox + values[0], oy + values[1]
            path.moveTo(x, y)
            start_x, start_y = x, y
            command = "l" if relative else "L"  # further pairs are lines
        elif upper == "L":
            x, y = ox + values[0], oy + values[1]
            path.lineTo(x, y)
        elif upper == "H":
            x = (x if relative else 0.0) + values[0]
            path.lineTo(x, y)
        elif upper == "V":
            y = (y if relative else 0.0) + values[0]
            path.lineTo(x, y)
        elif upper == "C":
            c1 = QPointF(ox + values[0], oy + values[1])
            control = QPointF(ox + values[2], oy + values[3])
            x, y = ox + values[4], oy + values[5]
            path.cubicTo(c1, control, QPointF(x, y))
        elif upper == "S":
            c1 = QPointF(2 * x - last_control.x(), 2 * y - last_control.y()) if last_control else QPointF(x, y)
            control = QPointF(ox + values[0], oy + values[1])
            x, y = ox + values[2], oy + values[3]
            path.cubicTo(c1, control, QPointF(x, y))
        elif upper == "Q":
            c1 = QPointF(ox + values[0], oy + values[1])
            x, y = ox + values[2], oy + values[3]
            path.quadTo(c1, QPointF(x, y))
        elif upper == "A":
            nx, ny = ox + values[5], oy + values[6]
            _arc(path, x, y, values[0], values[1], bool(values[3]), bool(values[4]), nx, ny)
            x, y = nx, ny
        last_control = control
    return path


def shapes(markup):
    """QPainterPaths for an icon written as SVG elements."""
    root = ElementTree.fromstring(f"<g>{markup}</g>")
    result = []
    for element in root:
        a = {key: float(value) if key != "d" else value for key, value in element.attrib.items()}
        path = QPainterPath()
        if element.tag == "path":
            path = path_from_svg(a["d"])
        elif element.tag == "rect":
            radius = a.get("rx", 0.0)
            path.addRoundedRect(QRectF(a["x"], a["y"], a["width"], a["height"]), radius, radius)
        elif element.tag == "circle":
            path.addEllipse(QPointF(a["cx"], a["cy"]), a["r"], a["r"])
        elif element.tag == "ellipse":
            path.addEllipse(QPointF(a["cx"], a["cy"]), a["rx"], a["ry"])
        result.append(path)
    return result


def paint_icon(painter, markup, color, size, stroke=1.8):
    """Draw an icon designed on a 24x24 grid into a size x size square."""
    from PyQt5.QtGui import QPen
    pen = QPen(color, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.save()
    painter.scale(size / 24.0, size / 24.0)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    for path in shapes(markup):
        painter.drawPath(path)
    painter.restore()
