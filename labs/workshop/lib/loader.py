"""Finding and reading the files Lab 08 uses. No statistics, no modelling.

The course keeps its data-science logic in the notebook, where it can be read and edited one
cell at a time. What lives here is the part that is the same on every machine and teaches
nothing: locating the repository root, opening a CSV, parsing a timestamp column.

Lab 08 starts from what Lab 01 published rather than from the raw telemetry:

    outputs/workshop/features.csv        one row per sample, every engineered feature
    outputs/workshop/feature_spec.json   every number Lab 01 chose or measured

Three files from the source data answer questions that contract does not carry:

    synthetic_rrd_metrics.csv     the raw counters, which the attenuation step needs
    synthetic_event_catalog.csv   which intervals were an incident, and of what kind
    change_calendar.csv           which intervals were announced in advance

The last one is what separates a fault from a change. Without it every scheduled backup is an
incident, and no detector can tell the difference, because on the wire there is none.
"""
import json
from pathlib import Path

import pandas as pd

DATA_SUBDIR = Path("data") / "synthetic"
PUBLISHED_SUBDIR = Path("outputs") / "workshop"


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


def load_feature_contract(root=None):
    """Lab 01's published frame and spec, sorted by port then time, index reset.

    Returns `(frame, spec)` rather than either alone, because a frame without the spec that
    describes it is the failure this pair exists to prevent: a notebook scoring columns whose
    definition it is guessing at. Every assertion the notebook makes is against the spec.
    """
    root = find_repo_root() if root is None else Path(root)
    published = root / PUBLISHED_SUBDIR
    frame = pd.read_csv(published / "features.csv", parse_dates=["timestamp"])
    frame = frame.sort_values(["port_id", "timestamp"]).reset_index(drop=True)
    spec = json.loads((published / "feature_spec.json").read_text())
    return frame, spec


def load_telemetry(root=None):
    """The month of raw counters, sorted by port then time, index reset.

    Lab 01's contract ships the engineered features but not the counters they came from. The
    attenuation step needs the counters, because weakening an incident has to happen before the
    ratios are formed or the resulting port is arithmetically impossible.
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
