"""Preenchimento de polígonos convexos em numpy, para os `RasterCanvas` que reproduzem o HUD sem GPU."""
import math

import numpy as np


def blend_polygon(frame, points, color):
    """Mistura `color` (r, g, b, a) sobre `frame` (altura x largura x 3, y para cima) dentro do polígono convexo
    `points`. Cobertura por centro de pixel, sem suavização, como a GPU sem MSAA."""
    height, width = frame.shape[:2]
    x0, x1 = max(0, math.floor(min(p[0] for p in points))), min(width, math.ceil(max(p[0] for p in points)))
    y0, y1 = max(0, math.floor(min(p[1] for p in points))), min(height, math.ceil(max(p[1] for p in points)))
    if x1 <= x0 or y1 <= y0:
        return
    px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    orientation = 1.0 if _signed_area(points) >= 0 else -1.0
    inside = np.ones(px.shape, bool)
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        inside &= ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) * orientation >= 0
    alpha = color[3]
    region = frame[y0:y1, x0:x1]
    region[inside] = region[inside] * (1.0 - alpha) + np.array(color[:3], np.float32) * alpha


def _signed_area(points):
    return sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]))
