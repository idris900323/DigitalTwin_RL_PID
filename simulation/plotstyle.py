"""One fixed colour, line style and marker per method, shared by every figure in the project.

Colours are the Okabe-Ito colour-blind-safe palette; line style and marker give redundant encoding so figures
survive greyscale printing. Add new methods to ``METHODS`` (append only: never reorder, so existing figures keep
their look). ``style(name)`` raises for an unknown name rather than silently inventing a style.
"""

from __future__ import annotations

OKABE_ITO = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000")
LINESTYLES = ("-", "--", "-.", ":")
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "*")

# Fixed-PID test sequence (simulate_pid.py) first, then tuning methods used in later groups.
METHODS = (
    "1 low P", "2a higher P", "2b highest P", "3 P+D (Tuned)", "4 P+I", "5 full PID", "legacy default",
    "analytic (IMC)", "optimised (nominal)", "optimised (robust)", "bandit RL", "step-wise RL", "oracle",
)


def style(name: str) -> dict:
    """matplotlib kwargs (color, linestyle, marker) for ``name``."""
    try:
        i = METHODS.index(name)
    except ValueError as exc:
        raise KeyError(f"no fixed style for method {name!r}; add it to simulation/plotstyle.METHODS") from exc
    return dict(color=OKABE_ITO[i % len(OKABE_ITO)], linestyle=LINESTYLES[(i // len(OKABE_ITO) + i) % len(LINESTYLES)],
                marker=MARKERS[i % len(MARKERS)])
