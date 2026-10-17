"""Characteristic-curve digitiser (G3B.2.5): turn pixel clicks on a datasheet plot into physical values.

``AxisCalibration`` maps one image axis from two reference points (pixel, value), linear or logarithmic.
``Digitizer`` combines an x and a y calibration. ``trace_curve`` also finds a curve of a given colour in an image array
automatically. The interactive picker (matplotlib ginput or a browser page) only has to collect the clicks; the tested logic
is here. Output is a point list with units that can go into a profile's ``curves`` section.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np


@dataclass
class AxisCalibration:
    pixel0: float
    value0: float
    pixel1: float
    value1: float
    log: bool = False

    def __post_init__(self):
        if self.pixel0 == self.pixel1:
            raise ValueError("the two calibration pixels must differ")
        if self.log and (self.value0 <= 0 or self.value1 <= 0):
            raise ValueError("a logarithmic axis needs positive calibration values")

    def to_value(self, pixel):
        t = (np.asarray(pixel, float) - self.pixel0) / (self.pixel1 - self.pixel0)
        if self.log:
            return np.exp(math.log(self.value0) + t * (math.log(self.value1) - math.log(self.value0)))
        return self.value0 + t * (self.value1 - self.value0)


@dataclass
class Digitizer:
    x: AxisCalibration
    y: AxisCalibration
    x_unit: str = ""
    y_unit: str = ""

    def convert(self, pixels: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
        p = np.asarray(pixels, float)
        return list(zip(self.x.to_value(p[:, 0]).tolist(), self.y.to_value(p[:, 1]).tolist()))


def trace_curve(image: np.ndarray, color: Tuple[int, int, int], tol: float = 60.0, step: int = 1) -> List[Tuple[float, float]]:
    """Pixel points (x, y) of the curve of ``color`` in an RGB image array: for each column, the mean row of matching pixels."""
    img = np.asarray(image)[..., :3].astype(float)
    mask = np.linalg.norm(img - np.asarray(color, float), axis=-1) < tol
    pts = []
    for x in range(0, mask.shape[1], step):
        rows = np.where(mask[:, x])[0]
        if len(rows):
            pts.append((float(x), float(rows.mean())))
    return pts
