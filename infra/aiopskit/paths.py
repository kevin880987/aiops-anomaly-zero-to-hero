"""Project path resolution.

Notebooks run from labs/workshop/, scripts run from the repository root, and
CI runs from somewhere else again. Every module resolves paths through here so
that a lab never depends on the working directory it happened to start in.
"""
from __future__ import annotations

import os
from pathlib import Path

_MARKER = "environment.yml"


def project_root(start: Path | str | None = None) -> Path:
    """Walk upwards until the repository marker file is found.

    Falls back to the AIOPS_PROJECT_ROOT environment variable, then to the
    package location, so that an unusual working directory does not break a lab.
    """
    env = os.environ.get("AIOPS_PROJECT_ROOT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if (candidate / _MARKER).exists():
            return candidate

    here = Path(start).resolve() if start else Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / _MARKER).exists():
            return candidate

    # infra/aiopskit/paths.py -> repository root is two levels up.
    fallback = Path(__file__).resolve().parents[2]
    if (fallback / _MARKER).exists():
        return fallback
    raise FileNotFoundError(
        f"Could not locate {_MARKER}. Set AIOPS_PROJECT_ROOT to the repository root."
    )


ROOT = project_root()

DATA_DIR = ROOT / "data" / "synthetic"
TELEMETRY_CSV = DATA_DIR / "synthetic_rrd_metrics.csv"
EVENT_CATALOG_CSV = DATA_DIR / "synthetic_event_catalog.csv"
CHANGE_CALENDAR_CSV = DATA_DIR / "change_calendar.csv"

OUTPUT_DIR = ROOT / "outputs" / "workshop"
DROPZONE_DIR = ROOT / "outputs" / "prometheus-dropzone"
DROPZONE_CSV = DROPZONE_DIR / "current_results.csv"
DROPZONE_MANIFEST = DROPZONE_DIR / "current_results.manifest.json"
REPLAY_STATE = DROPZONE_DIR / "replay_state.json"

GRAFANA_DASHBOARD_DIR = ROOT / "infra" / "grafana" / "dashboards"


def ensure_dirs() -> None:
    for directory in (OUTPUT_DIR, DROPZONE_DIR, GRAFANA_DASHBOARD_DIR):
        directory.mkdir(parents=True, exist_ok=True)
