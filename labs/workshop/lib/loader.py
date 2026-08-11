"""Finding and reading the three files Lab 08 uses. No statistics, no modelling.

The course keeps its data-science logic in the notebook, where it can be read and edited one
cell at a time. What lives here is the part that is the same on every machine and teaches
nothing: locating the repository root, opening a CSV, parsing a timestamp column.

Three files, and each answers a different question:

    synthetic_rrd_metrics.csv     what the ports did, per 5-minute interval
    synthetic_event_catalog.csv   which of those intervals were an incident, and of what kind
    change_calendar.csv           which of those intervals were announced in advance

The third file is what separates a fault from a change. Without it every scheduled backup is an
incident, and no detector can tell the difference, because on the wire there is none.
"""
from pathlib import Path

import pandas as pd

DATA_SUBDIR = Path("data") / "synthetic"


def find_repo_root(start=None):
    """Walk upward until the folder holding data/synthetic appears.

    Same idiom Lab 04 and Lab 05 open with, so a notebook runs from its own directory or from
    the repository root without either one being the blessed one.
    """
    start = Path.cwd() if start is None else Path(start)
    for candidate in (start, *start.parents):
        if (candidate / DATA_SUBDIR / "synthetic_rrd_metrics.csv").exists():
            return candidate
    raise FileNotFoundError(
        f"cannot locate the repository root: no ancestor of {start} contains "
        f"{DATA_SUBDIR / 'synthetic_rrd_metrics.csv'}")


def _read(name, root, **kwargs):
    root = find_repo_root() if root is None else Path(root)
    return pd.read_csv(root / DATA_SUBDIR / name, **kwargs)


def load_telemetry(root=None):
    """The month of port telemetry, sorted by port then time, index reset.

    The index is reset so a numpy array of the same length lines up with the frame. Nothing is
    computed, converted or validated here; the notebook's first step does that, because deciding
    whether a column reads as a counter or as an interval total is the first thing a cadet has to
    do for themselves.
    """
    frame = _read("synthetic_rrd_metrics.csv", root, parse_dates=["timestamp"])
    return frame.sort_values(["port_id", "timestamp"]).reset_index(drop=True)


def load_catalog(root=None):
    """The incident catalog: one row per labelled incident, with its engineering description."""
    return _read("synthetic_event_catalog.csv", root, parse_dates=["start_time", "end_time"])


def load_calendar(root=None):
    """The change calendar: what operations announced in advance, and over which scope.

    `scope` holds a port_id on some rows and a device_id on others, which is how a change is
    actually filed. Resolving that against the telemetry is a judgement call, so it belongs in
    the notebook rather than here.
    """
    return _read("change_calendar.csv", root, parse_dates=["start_time", "end_time"])
