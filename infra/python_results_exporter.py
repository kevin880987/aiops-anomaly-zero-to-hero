#!/usr/bin/env python3
"""
Expose notebook-generated CSV results as Prometheus metrics.

Use this when a lab writes anomaly scores, flags, forecasts, or SPC results
under outputs/. Prometheus scrapes this exporter; Grafana then queries
aiops_python_result.

Examples:
    python infra/python_results_exporter.py

    cp outputs/self-study/ml_anomaly_scores.csv outputs/prometheus-dropzone/current_results.csv

    RESULTS_CSV_PATH=outputs/self-study/forecast_results.csv \
    RESULT_COLUMNS=y_hat,y_hat_lower,y_hat_upper,forecast_30m,early_warning_30m \
    python infra/python_results_exporter.py
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
from prometheus_client import Gauge, start_http_server

REPO_ROOT = Path(__file__).resolve().parents[1]
DROPZONE_PATH = REPO_ROOT / "outputs" / "prometheus-dropzone" / "current_results.csv"
CSV_PATH = Path(os.environ.get("RESULTS_CSV_PATH", DROPZONE_PATH))
if not CSV_PATH.is_absolute():
    CSV_PATH = REPO_ROOT / CSV_PATH

PORT = int(os.environ.get("RESULTS_EXPORTER_PORT", "8010"))
REPLAY_SPEED_X = float(os.environ.get("REPLAY_SPEED_X", "3600"))
CONFIGURED_VALUE_COLUMNS = [
    col.strip()
    for col in os.environ.get("RESULT_COLUMNS", "").split(",")
    if col.strip()
]
DEFAULT_LABEL_COLUMNS = ["device_id", "port_id", "port_role", "event_label", "ml_method"]
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


def infer_value_columns(df: pd.DataFrame) -> list[str]:
    if CONFIGURED_VALUE_COLUMNS:
        missing = [col for col in CONFIGURED_VALUE_COLUMNS if col not in df.columns]
        if missing:
            raise SystemExit(f"{CSV_PATH} does not contain RESULT_COLUMNS: {missing}")
        return CONFIGURED_VALUE_COLUMNS

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


def load_results(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        return pd.DataFrame(), []
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise SystemExit(f"{path} must contain a timestamp column.")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    value_columns = infer_value_columns(df)
    return df.sort_values("timestamp").reset_index(drop=True), value_columns


df, value_columns = load_results(CSV_PATH)
csv_mtime = CSV_PATH.stat().st_mtime if CSV_PATH.exists() else None
sim_start = df["timestamp"].min() if not df.empty else None
sim_end = df["timestamp"].max() if not df.empty else None

result_value = Gauge(
    "aiops_python_result",
    "Notebook-generated AIOps result exposed for Grafana.",
    ["source", "column", *LABEL_COLUMNS],
)
result_timestamp = Gauge(
    "aiops_python_result_timestamp",
    "Current simulated timestamp for Python result exporter.",
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


def reload_if_changed() -> None:
    global df, value_columns, csv_mtime, sim_start, sim_end
    if not CSV_PATH.exists():
        if csv_mtime is not None:
            df = pd.DataFrame()
            value_columns = []
            csv_mtime = None
            sim_start = None
            sim_end = None
            if hasattr(result_value, "clear"):
                result_value.clear()
            elif hasattr(result_value, "_metrics"):
                result_value._metrics.clear()
            print(f"Waiting for {CSV_PATH}")
        return
    current_mtime = CSV_PATH.stat().st_mtime
    if current_mtime == csv_mtime:
        return
    df, value_columns = load_results(CSV_PATH)
    csv_mtime = current_mtime
    sim_start = df["timestamp"].min()
    sim_end = df["timestamp"].max()
    if hasattr(result_value, "clear"):
        result_value.clear()
    elif hasattr(result_value, "_metrics"):
        result_value._metrics.clear()
    print(f"Reloaded {CSV_PATH}")
    print(f"Value columns: {', '.join(value_columns)}")


def current_window_rows(t: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    before = df[df["timestamp"] <= t]
    if before.empty:
        return df.head(0)
    latest_ts = before["timestamp"].max()
    return before[before["timestamp"] == latest_ts]


def label_values(row: pd.Series) -> list[str]:
    values = []
    for col in LABEL_COLUMNS:
        value = row.get(col, "")
        values.append("" if pd.isna(value) else str(value))
    return values


start_http_server(PORT)
print(f"Watching Python results CSV: {CSV_PATH}")
if value_columns:
    print(f"Value columns: {', '.join(value_columns)}")
else:
    print("No CSV loaded yet. Copy a lab output CSV to outputs/prometheus-dropzone/current_results.csv.")
print(f"Label columns: {', '.join(LABEL_COLUMNS)}")
print(f"Metrics endpoint: http://localhost:{PORT}/metrics")
print("Press Ctrl+C to stop.")

wall_start = time.time()

try:
    while True:
        reload_if_changed()
        t = current_sim_time(wall_start)
        result_timestamp.set(t.timestamp())
        rows = current_window_rows(t)

        for _, row in rows.iterrows():
            labels = label_values(row)
            for col in value_columns:
                value = row[col]
                if pd.isna(value):
                    continue
                result_value.labels(CSV_PATH.name, col, *labels).set(float(value))

        time.sleep(5)
except KeyboardInterrupt:
    print("\nStopped.")
