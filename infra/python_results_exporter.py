#!/usr/bin/env python3
"""
Expose notebook-generated CSV results as Prometheus metrics.

Use this when a lab writes anomaly scores, flags, forecasts, or SPC results
under outputs/. Prometheus scrapes this exporter; Grafana then queries
aiops_python_result.

The CSV is replayed against wall-clock time: each real second advances the
simulated clock by REPLAY_SPEED_X seconds, so a month of 5-minute telemetry
becomes a dashboard that moves during a class. The mapping is written to
outputs/prometheus-dropzone/replay_state.json so that a notebook placing Grafana
annotations can land them on the same timeline.

Workshop labs write the CSV through aiopskit.grafana.publish, which drops a
manifest next to it naming the columns to expose. Without a manifest the
exporter falls back to the historical column-guessing behaviour.

Examples:
    REPLAY_SPEED_X=720 python infra/python_results_exporter.py

    cp outputs/self-study/ml_anomaly_scores.csv outputs/prometheus-dropzone/current_results.csv

    RESULTS_CSV_PATH=outputs/self-study/forecast_results.csv \
    RESULT_COLUMNS=y_hat,y_hat_lower,y_hat_upper,forecast_30m,early_warning_30m \
    python infra/python_results_exporter.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from prometheus_client import Gauge, start_http_server

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aiops_contract as contract  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DROPZONE_PATH = REPO_ROOT / "outputs" / contract.DROPZONE_DIRNAME / contract.RESULT_CSV_NAME
CSV_PATH = Path(os.environ.get("RESULTS_CSV_PATH", DROPZONE_PATH))
if not CSV_PATH.is_absolute():
    CSV_PATH = REPO_ROOT / CSV_PATH

MANIFEST_PATH = CSV_PATH.with_suffix(".manifest.json")
REPLAY_STATE_PATH = DROPZONE_PATH.parent / contract.REPLAY_STATE_NAME

PORT = int(os.environ.get("RESULTS_EXPORTER_PORT", "8010"))
REPLAY_SPEED_X = float(os.environ.get("REPLAY_SPEED_X", "3600"))
MAX_SERIES = int(os.environ.get("RESULT_MAX_SERIES", "40"))
CONFIGURED_VALUE_COLUMNS = [
    col.strip()
    for col in os.environ.get("RESULT_COLUMNS", "").split(",")
    if col.strip()
]
DEFAULT_LABEL_COLUMNS = contract.LABEL_COLUMNS
LABEL_COLUMNS = [
    col.strip()
    for col in os.environ.get("RESULT_LABEL_COLUMNS", ",".join(DEFAULT_LABEL_COLUMNS)).split(",")
    if col.strip()
]
PREFERRED_VALUE_COLUMNS = [
    "ml_anomaly_score",
    "ml_is_anomaly",
    "y_hat",
    "y_hat_lower",
    "y_hat_upper",
    "forecast_30m",
    "early_warning_30m",
    "traffic_center",
    "traffic_ucl",
    "traffic_lcl",
    "shewhart_traffic_violation",
    "ewma_discard_violation",
    "cusum_error_violation",
    "severity_score",
    "raw_alert_count",
]


def read_manifest() -> dict:
    """Column list written alongside the CSV by aiopskit.grafana.publish.

    Guessing which columns matter works until a lab publishes twenty of them and
    the interesting one is not in the first eight. An explicit manifest removes
    that failure mode; the guessing path stays for hand-copied CSVs.
    """
    try:
        return json.loads(MANIFEST_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def infer_value_columns(df: pd.DataFrame, manifest: dict) -> list[str]:
    if CONFIGURED_VALUE_COLUMNS:
        missing = [col for col in CONFIGURED_VALUE_COLUMNS if col not in df.columns]
        if missing:
            raise SystemExit(f"{CSV_PATH} does not contain RESULT_COLUMNS: {missing}")
        return CONFIGURED_VALUE_COLUMNS

    declared = [col for col in manifest.get("value_columns", []) if col in df.columns]
    if declared:
        return declared

    preferred = [col for col in PREFERRED_VALUE_COLUMNS if col in df.columns]
    if preferred:
        return preferred

    excluded = {"timestamp", *LABEL_COLUMNS}
    numeric = [
        col for col in df.select_dtypes(include="number").columns
        if col not in excluded
    ]
    if not numeric:
        raise SystemExit(
            f"{CSV_PATH} has no numeric result columns. "
            "Set RESULT_COLUMNS to one or more numeric columns."
        )
    return numeric[:8]


def active_label_columns(df: pd.DataFrame, manifest: dict) -> list[str]:
    """Label columns present in this CSV; the rest are exported as empty strings.

    The Gauge is created once with a fixed label set, so the schema cannot change
    between reloads. Restricting which ones carry a value keeps the series count
    down when a lab publishes a single toy signal.
    """
    declared = manifest.get("label_columns")
    candidates = declared if declared else LABEL_COLUMNS
    return [col for col in candidates if col in df.columns]


def write_replay_state(wall_start: float) -> None:
    """Publish the sim-clock mapping so notebooks can align annotations to it."""
    if sim_start is None or sim_end is None:
        return
    REPLAY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLAY_STATE_PATH.write_text(json.dumps({
        "wall_start": wall_start,
        "sim_start": str(sim_start),
        "sim_end": str(sim_end),
        "speed_x": REPLAY_SPEED_X,
        "csv": CSV_PATH.name,
        "pass_duration_min": round((sim_end - sim_start).total_seconds() / REPLAY_SPEED_X / 60, 2),
    }, indent=2))


def load_results(path: Path) -> tuple[pd.DataFrame, list[str], list[str]]:
    if not path.exists():
        return pd.DataFrame(), [], []
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise SystemExit(f"{path} must contain a timestamp column.")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    manifest = read_manifest()
    value_columns = infer_value_columns(df, manifest)
    labels_present = active_label_columns(df, manifest)
    return df.sort_values("timestamp").reset_index(drop=True), value_columns, labels_present


df, value_columns, label_columns_present = load_results(CSV_PATH)
csv_mtime = CSV_PATH.stat().st_mtime if CSV_PATH.exists() else None
sim_start = df["timestamp"].min() if not df.empty else None
sim_end = df["timestamp"].max() if not df.empty else None
last_label_keys: set = set()

result_value = Gauge(
    contract.RESULT_METRIC,
    contract.METRIC_HELP[contract.RESULT_METRIC],
    ["source", "column", *LABEL_COLUMNS],
)
result_timestamp = Gauge(
    contract.RESULT_TIMESTAMP_METRIC,
    contract.METRIC_HELP[contract.RESULT_TIMESTAMP_METRIC],
)
replay_progress = Gauge(
    contract.REPLAY_PROGRESS_METRIC,
    contract.METRIC_HELP[contract.REPLAY_PROGRESS_METRIC],
)
replay_speed = Gauge(
    contract.REPLAY_SPEED_METRIC,
    contract.METRIC_HELP[contract.REPLAY_SPEED_METRIC],
)
result_rows = Gauge(
    contract.RESULT_ROWS_METRIC,
    contract.METRIC_HELP[contract.RESULT_ROWS_METRIC],
)


def current_sim_time(wall_start: float) -> pd.Timestamp:
    if sim_start is None or sim_end is None:
        return pd.Timestamp.now("UTC")
    elapsed = (time.time() - wall_start) * REPLAY_SPEED_X
    t = sim_start + pd.Timedelta(seconds=elapsed)
    if t > sim_end:
        span = sim_end - sim_start
        if span.total_seconds() > 0:
            t = sim_start + (t - sim_start) % span
        else:
            t = sim_start
    return t


def clear_series() -> None:
    if hasattr(result_value, "clear"):
        result_value.clear()
    elif hasattr(result_value, "_metrics"):
        result_value._metrics.clear()


def reload_if_changed(wall_start: float) -> None:
    global df, value_columns, label_columns_present, csv_mtime, sim_start, sim_end, last_label_keys
    if not CSV_PATH.exists():
        if csv_mtime is not None:
            df = pd.DataFrame()
            value_columns = []
            label_columns_present = []
            csv_mtime = None
            sim_start = None
            sim_end = None
            last_label_keys = set()
            clear_series()
            print(f"Waiting for {CSV_PATH}")
        return
    current_mtime = CSV_PATH.stat().st_mtime
    if current_mtime == csv_mtime:
        return
    df, value_columns, label_columns_present = load_results(CSV_PATH)
    csv_mtime = current_mtime
    sim_start = df["timestamp"].min()
    sim_end = df["timestamp"].max()
    last_label_keys = set()
    clear_series()
    result_rows.set(len(df))
    write_replay_state(wall_start)
    print(f"Reloaded {CSV_PATH} ({len(df):,} rows)")
    print(f"Value columns: {', '.join(value_columns)}")
    print(f"Active labels: {', '.join(label_columns_present) or '(none)'}")


def current_window_rows(t: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    before = df[df["timestamp"] <= t]
    if before.empty:
        return df.head(0)
    latest_ts = before["timestamp"].max()
    return before[before["timestamp"] == latest_ts]


def label_values(row: pd.Series) -> tuple[str, ...]:
    """Only columns the manifest declared carry a value; the rest stay empty.

    The Gauge label set is fixed at construction, so a column missing from this
    CSV has to be exported as an empty string rather than dropped.
    """
    values = []
    for col in LABEL_COLUMNS:
        if col not in label_columns_present:
            values.append("")
            continue
        value = row.get(col, "")
        values.append("" if pd.isna(value) else str(value))
    return tuple(values)


start_http_server(PORT)
print(f"Watching Python results CSV: {CSV_PATH}")
if value_columns:
    print(f"Value columns: {', '.join(value_columns)}")
else:
    print("No CSV loaded yet. Publish from a workshop notebook, or copy a lab output CSV to")
    print(f"  {DROPZONE_PATH.relative_to(REPO_ROOT)}")
print(f"Label columns: {', '.join(LABEL_COLUMNS)}")
print(f"Replay speed: {REPLAY_SPEED_X:g}x real time")
print(f"Metrics endpoint: http://localhost:{PORT}/metrics")
print("Press Ctrl+C to stop.")

wall_start = time.time()
replay_speed.set(REPLAY_SPEED_X)
result_rows.set(len(df))
write_replay_state(wall_start)
if sim_start is not None and sim_end is not None:
    print(f"One full pass takes {(sim_end - sim_start).total_seconds() / REPLAY_SPEED_X / 60:.1f} real minutes.")

try:
    while True:
        reload_if_changed(wall_start)
        t = current_sim_time(wall_start)
        result_timestamp.set(t.timestamp())
        if sim_start is not None and sim_end is not None and sim_end > sim_start:
            replay_progress.set((t - sim_start).total_seconds() / (sim_end - sim_start).total_seconds())

        rows = current_window_rows(t)

        # A label whose value changes over the replay, event_label being the
        # obvious one, would otherwise leave the previous series behind holding
        # its last value forever. Clearing only when the label set actually
        # changes keeps that from happening without churning the registry on
        # every tick.
        keys = {(col, label_values(row)) for _, row in rows.iterrows() for col in value_columns}
        if keys != last_label_keys:
            clear_series()
            last_label_keys = keys

        emitted = 0
        for _, row in rows.iterrows():
            labels = label_values(row)
            for col in value_columns:
                value = row[col]
                if pd.isna(value):
                    continue
                result_value.labels(CSV_PATH.name, col, *labels).set(float(value))
                emitted += 1
                if emitted >= MAX_SERIES * len(value_columns):
                    break

        time.sleep(5)
except KeyboardInterrupt:
    print("\nStopped.")
