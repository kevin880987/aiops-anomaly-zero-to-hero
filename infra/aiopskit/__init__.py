"""aiopskit: the plumbing for the AIOps workshop labs.

The split is deliberate. This package owns loading, publishing, plotting,
Grafana wiring and scoring -- work that must be identical for every cadet so
that two people comparing thresholds are comparing thresholds and not two
different implementations of a rolling median.

The algorithm stays in the notebook. Baselines, detectors and policies are
exposed as small functions a cadet reads, calls, and argues with, not as a
`fit()` that hides the decision being taught.

    import sys, pathlib
    sys.path.insert(0, str(PROJECT_ROOT / "infra"))
    import aiopskit as wk

    telemetry, contract = wk.load_telemetry()
    print(contract.describe())
"""
from __future__ import annotations

from . import baselines, data, detect, evaluate, grafana, paths, viz
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
from .grafana import GrafanaClient, ReplayClock, check_stack, deploy, event_annotations, publish
from .viz import Band, PanelSpec, Series, ThresholdLine, render, render_stack

__all__ = [
    "baselines", "data", "detect", "evaluate", "grafana", "paths", "viz",
    "load_telemetry", "load_events", "load_change_calendar", "split_events", "single_port",
    "truth_mask", "in_change_window", "infer_cadence", "synthetic_wave",
    "confirm", "build_alerts", "AlertPolicy", "notification_text",
    "score", "point_metrics", "sweep", "comparison_table",
    "publish", "deploy", "check_stack", "GrafanaClient", "ReplayClock", "event_annotations",
    "PanelSpec", "Series", "Band", "ThresholdLine", "render", "render_stack",
]

__version__ = "1.0.0"


def bootstrap(quiet: bool = False):
    """Standard first cell for every workshop lab.

    Resolves the repository root, makes sure the output directories exist, and
    reports which services are reachable so that a cadet finds out about a
    stopped exporter now rather than forty minutes later.
    """
    paths.ensure_dirs()
    if not quiet:
        print(f"project root  {paths.ROOT}")
        print(f"aiopskit      {__version__}")
        print()
        grafana.check_stack(verbose=True)
    return paths.ROOT
