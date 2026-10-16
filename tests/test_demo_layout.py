"""G1.3: the matplotlib demo's plots, metrics text and sliders must not overlap."""

import itertools

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from simulation.interactive_pid_twin import build_figure
from tests.helpers import load_config

SIZES_PX = [(800, 800), (1000, 700), (1600, 900)]  # default, small, large window


def _overlap(a, b, pad=0.0):
    return not (a.x1 + pad <= b.x0 or b.x1 + pad <= a.x0 or a.y1 + pad <= b.y0 or b.y1 + pad <= a.y0)


@pytest.mark.parametrize("w,h", SIZES_PX)
def test_no_overlap(w, h):
    fig, widgets, axes, metrics_text = build_figure(load_config(), figsize=(w / 100, h / 100))
    fig.set_dpi(100)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()

    boxes = {
        "theta": axes["theta"].get_tightbbox(r),
        "err": axes["err"].get_tightbbox(r),
        "v": axes["v"].get_tightbbox(r),
        "metrics_text": metrics_text.get_window_extent(r),
    }
    for name, s in zip(("kp", "ki", "kd"), widgets):
        a = s.ax.get_window_extent(r)
        parts = [a, s.label.get_window_extent(r), s.valtext.get_window_extent(r)]
        boxes[name] = matplotlib.transforms.Bbox.union(parts)

    for (na, ba), (nb, bb) in itertools.combinations(boxes.items(), 2):
        assert not _overlap(ba, bb), f"{na} overlaps {nb} at {w}x{h}"

    fig_box = fig.bbox
    for name, b in boxes.items():
        assert b.x0 >= fig_box.x0 - 1 and b.x1 <= fig_box.x1 + 1, f"{name} outside figure horizontally at {w}x{h}"
        assert b.y0 >= fig_box.y0 - 1 and b.y1 <= fig_box.y1 + 1, f"{name} outside figure vertically at {w}x{h}"
    plt.close(fig)
