#!/usr/bin/env python3
"""
Standalone RRD metrics exporter for aiops-anomaly-zero-to-hero.

Replays synthetic_rrd_metrics.csv as a live Prometheus metrics stream.
Each real second advances the simulation by REPLAY_SPEED_X seconds.

Usage:
    conda activate aiops-anomaly-zero-to-hero
    python infra/rrd_exporter.py

Environment variables:
    CSV_PATH        Path to synthetic_rrd_metrics.csv  (default: data/synthetic/synthetic_rrd_metrics.csv)
    EXPORTER_PORT   Port to expose /metrics on          (default: 8000)
    REPLAY_SPEED_X  Simulation speed multiplier         (default: 3600 → 1 real sec = 1 sim hour)
"""
import os
import time
from pathlib import Path

import pandas as pd
from prometheus_client import Gauge, start_http_server

# ── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH  = Path(os.environ.get("CSV_PATH",
    REPO_ROOT / "data" / "synthetic" / "synthetic_rrd_metrics.csv"))
PORT           = int(os.environ.get("EXPORTER_PORT", 8000))
REPLAY_SPEED_X = float(os.environ.get("REPLAY_SPEED_X", 3600))

METRIC_COLS = [
    "INOCTETS", "OUTOCTETS", "INERRORS", "OUTERRORS",
    "INUCASTPKTS", "OUTUCASTPKTS", "INNUCASTPKTS", "OUTNUCASTPKTS",
    "INDISCARDS", "OUTDISCARDS", "INUNKNOWNPROTOS",
    "INBROADCASTPKTS", "OUTBROADCASTPKTS",
    "INMULTICASTPKTS", "OUTMULTICASTPKTS",
]
LABELS = ["device_id", "port_id", "port_role"]
EVENT_LABELS = ["device_id", "port_id", "port_role", "event_id", "event_label"]

# ── Load CSV ──────────────────────────────────────────────────────────────────
if not CSV_PATH.exists():
    raise SystemExit(f"CSV not found: {CSV_PATH}\nRun the simulator notebook first.")

print(f"Loading {CSV_PATH} …")
df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
df = df.sort_values(["port_id", "timestamp"]).reset_index(drop=True)

sim_start = df["timestamp"].min()
sim_end   = df["timestamp"].max()
print(f"Simulation span: {sim_start} → {sim_end}")
print(f"Replay speed: {REPLAY_SPEED_X}× real-time")
print(f"Full replay duration: "
      f"{(sim_end - sim_start).total_seconds() / REPLAY_SPEED_X / 60:.1f} real minutes")

# ── Prometheus gauges ─────────────────────────────────────────────────────────
gauges = {
    col: Gauge(
        f"network_rrd_{col.lower()}",
        f"Network RRD metric: {col}",
        LABELS,
    )
    for col in METRIC_COLS
}
simulated_timestamp = Gauge(
    "network_rrd_simulated_timestamp",
    "Current simulated timestamp as Unix seconds.",
)
event_gauge = Gauge(
    "network_rrd_event",
    "Active synthetic event marker. Value is 1 for the current event and 0 otherwise.",
    EVENT_LABELS,
)

# ── Helpers ───────────────────────────────────────────────────────────────────
def current_sim_time(wall_start: float) -> pd.Timestamp:
    elapsed = (time.time() - wall_start) * REPLAY_SPEED_X
    t = sim_start + pd.Timedelta(seconds=elapsed)
    if t > sim_end:
        t = sim_start + (t - sim_start) % (sim_end - sim_start)
    return t.floor("s")

def nearest_row(port_df: pd.DataFrame, t: pd.Timestamp) -> pd.Series | None:
    idx = port_df["timestamp"].searchsorted(t, side="right") - 1
    if idx < 0:
        return None
    return port_df.iloc[idx]

# ── Main loop ─────────────────────────────────────────────────────────────────
start_http_server(PORT)
print(f"\nExporting metrics on http://localhost:{PORT}/metrics")
print("Press Ctrl+C to stop.\n")

ports = {pid: grp.reset_index(drop=True) for pid, grp in df.groupby("port_id")}
port_events = {}
for port_id, grp in df.groupby("port_id"):
    event_rows = grp[["device_id", "port_id", "port_role", "event_id", "event_label"]].drop_duplicates()
    port_events[port_id] = [
        [
            str(row["device_id"]),
            str(row["port_id"]),
            str(row["port_role"]),
            str(row["event_id"]),
            str(row["event_label"]),
        ]
        for _, row in event_rows.iterrows()
        if str(row["event_label"]) != "normal"
    ]
wall_start = time.time()

try:
    while True:
        t = current_sim_time(wall_start)
        simulated_timestamp.set(t.timestamp())
        for port_id, port_df in ports.items():
            row = nearest_row(port_df, t)
            if row is None:
                continue
            lv = [row["device_id"], row["port_id"], row["port_role"]]
            for col, gauge in gauges.items():
                v = row.get(col)
                if v is not None and not pd.isna(v):
                    gauge.labels(*lv).set(float(v))
            current_event = str(row.get("event_label", "normal"))
            current_event_id = str(row.get("event_id", "normal"))
            for event_labels in port_events.get(port_id, []):
                event_gauge.labels(*event_labels).set(0)
            if current_event != "normal":
                event_gauge.labels(
                    str(row["device_id"]),
                    str(row["port_id"]),
                    str(row["port_role"]),
                    current_event_id,
                    current_event,
                ).set(1)
        time.sleep(5)
except KeyboardInterrupt:
    print("\nStopped.")
