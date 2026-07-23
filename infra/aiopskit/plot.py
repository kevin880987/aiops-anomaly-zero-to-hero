"""Two things worth sharing between notebooks: a house style and a shading helper.

Everything else about a chart is plain matplotlib, written out in the cell that
produces the result, because that is what a cadet can carry to work. The shared
pieces are the ones that are pure boilerplate to repeat: the serif house style
that keeps every figure looking like the rest of the course material, and the
run-shading helper, which done naively draws one rectangle per sample and
repeats the legend entry for each one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The workshop palette, named so a cadet can reach for a colour by meaning rather
# than by hex. Matches the Grafana panel colours in the dashboard JSON.
PALETTE = {
    "signal": "#3B7DD8", "baseline": "#E0752D", "score": "#7A5AC7",
    "alert": "#D6455D", "truth": "#7C8A99", "peer": "#2E9E7B", "muted": "#9AA4B0",
}


def house_style() -> None:
    """Set a serif house style for every figure the notebook draws.

    Serif to match the diagrams and the printed course notes, muted grid, no top
    or right spine. `bootstrap` calls this, so a workshop lab inherits it without
    a per-notebook line; call it again by hand after any `plt.style.use`.
    """
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "figure.dpi": 110,
        "axes.titlesize": 11, "axes.titleweight": "normal", "axes.titlelocation": "left",
        "axes.labelsize": 9, "legend.fontsize": 8, "legend.framealpha": 0.85,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.grid": True, "grid.alpha": 0.22, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def shade_truth(ax, time, mask, color: str = "#7C8A99", alpha: float = 0.18,
                legend: str = "ground truth") -> None:
    """Shade the contiguous spans where `mask` is true, as a single legend entry."""
    values = np.asarray(pd.Series(mask).fillna(False), dtype=bool)
    index = np.flatnonzero(values)
    if index.size == 0:
        return
    breaks = np.flatnonzero(np.diff(index) > 1)
    starts = np.concatenate([[index[0]], index[breaks + 1]])
    ends = np.concatenate([index[breaks], [index[-1]]])
    time = pd.Series(time).reset_index(drop=True)
    for n, (a, b) in enumerate(zip(starts, ends)):
        ax.axvspan(time.iloc[a], time.iloc[b], color=color, alpha=alpha,
                   linewidth=0, zorder=0, label=legend if n == 0 else None)
