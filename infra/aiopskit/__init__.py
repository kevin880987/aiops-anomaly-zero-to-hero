"""aiopskit: the analysis half of the AIOps workshop.

This package holds the parts a cadet should not have to re-implement to
compare notes with the person next to them: the data contract, the baselines,
the detectors, the alert policy and the evaluation metrics. Two people arguing
about a threshold are then arguing about a threshold, not about two different
rolling medians.

It deliberately owns nothing else. Charts are plain matplotlib in the notebook.
Results reach Grafana as a CSV file written with `to_csv` and served by
`python -m http.server`, so there is no exporter, no client and no dashboard
generator here to take on trust.

The algorithm stays in the notebook too. Baselines, detectors and policies are
small functions a cadet reads, calls and argues with, rather than a `fit()`
that hides the decision being taught.

    import sys, pathlib
    sys.path.insert(0, str(PROJECT_ROOT / "infra"))
    import aiopskit as wk

    telemetry, contract = wk.load_telemetry()
    print(contract.describe())
"""
from __future__ import annotations

from . import baselines, data, detect, evaluate, paths
from .data import (
    infer_cadence,
    in_change_window,
    load_change_calendar,
    load_events,
    load_telemetry,
    single_port,
    split_events,
    synthetic_wave,
    truth_mask,
)
from .detect import AlertPolicy, build_alerts, confirm, notification_text
from .evaluate import comparison_table, evaluate as score, point_metrics, sweep
from .plot import PALETTE, house_style, shade_truth

__all__ = [
    "baselines", "data", "detect", "evaluate", "paths",
    "load_telemetry", "load_events", "load_change_calendar", "split_events", "single_port",
    "truth_mask", "in_change_window", "infer_cadence", "synthetic_wave",
    "confirm", "build_alerts", "AlertPolicy", "notification_text",
    "score", "point_metrics", "sweep", "comparison_table",
    "shade_truth", "house_style", "PALETTE",
]

__version__ = "2.0.0"


def bootstrap(quiet: bool = False):
    """Standard first cell for every workshop lab.

    Resolves the repository root, makes sure the output directory exists, and
    sets the serif house style so every figure in the lab matches the course
    material. It does not probe Grafana or Prometheus: those are checked by
    opening them, which is the same thing a cadet will do at work.
    """
    paths.ensure_dirs()
    house_style()
    if not quiet:
        print(f"project root  {paths.ROOT}")
        print(f"outputs       {paths.OUTPUT_DIR}")
        print(f"aiopskit      {__version__}")
        print("figure style  serif house style applied (wk.house_style)")
    return paths.ROOT
