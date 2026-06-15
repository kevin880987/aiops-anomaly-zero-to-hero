"""
Prometheus metrics exporter for the aiops-monitor package.

Reads a synthetic RRD-like CSV and replays it in accelerated real time so
anomalies (spanning hours in the CSV) appear within minutes on a live
Grafana dashboard.

Replay speed
------------
REPLAY_SPEED_X (default 60) means 60 simulated seconds elapse per real second.
At 60×, the full 30-day dataset cycles in 12 real hours.
Set REPLAY_SPEED_X=720 for a ~60-minute demo cycle.

Entry point
-----------
    aiops-export          # installed CLI
    python -m aiops_monitor.exporter.metrics_exporter
"""

from __future__ import annotations

import os
import time

import pandas as pd
from prometheus_client import Gauge, start_http_server

# ── Configuration (all overridable via environment variables) ────────────────
CSV_PATH        = os.environ.get("CSV_PATH",           "/data/synthetic_rrd_metrics.csv")
PORT            = int(os.environ.get("EXPORTER_PORT",  "8000"))
REPLAY_SPEED_X  = float(os.environ.get("REPLAY_SPEED_X", "60"))
SCRAPE_INTERVAL = float(os.environ.get("SCRAPE_INTERVAL_S", "5"))

# ── Prometheus metric definitions ────────────────────────────────────────────
_L = ["device_id", "port_id", "port_role"]

rrd_in_octets    = Gauge("network_rrd_in_octets",           "Inbound octets per interval",       _L)
rrd_out_octets   = Gauge("network_rrd_out_octets",          "Outbound octets per interval",      _L)
rrd_in_errors    = Gauge("network_rrd_in_errors",           "Inbound error count",               _L)
rrd_out_errors   = Gauge("network_rrd_out_errors",          "Outbound error count",              _L)
rrd_in_pkts      = Gauge("network_rrd_in_ucast_pkts",       "Inbound unicast packets",           _L)
rrd_out_pkts     = Gauge("network_rrd_out_ucast_pkts",      "Outbound unicast packets",          _L)
rrd_in_discards  = Gauge("network_rrd_in_discards",         "Inbound discards",                  _L)
rrd_out_discards = Gauge("network_rrd_out_discards",        "Outbound discards",                 _L)
rrd_in_bcast     = Gauge("network_rrd_in_broadcast_pkts",   "Inbound broadcast packets",         _L)
rrd_out_bcast    = Gauge("network_rrd_out_broadcast_pkts",  "Outbound broadcast packets",        _L)
rrd_in_mcast     = Gauge("network_rrd_in_multicast_pkts",   "Inbound multicast packets",         _L)
rrd_out_mcast    = Gauge("network_rrd_out_multicast_pkts",  "Outbound multicast packets",        _L)
rrd_event        = Gauge("network_rrd_event",               "Current event label (1 = active)",  _L + ["event_label"])
rrd_sim_ts       = Gauge("network_rrd_simulated_timestamp", "Simulated time (Unix seconds)")


# ── Internal helpers ─────────────────────────────────────────────────────────

def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["event_label"] = df["event_label"].fillna("normal")
    return df


def _interval_s(df: pd.DataFrame) -> float:
    """Infer polling interval from the first two distinct timestamps."""
    ts = sorted(df["timestamp"].unique())
    if len(ts) < 2:
        raise ValueError("The metrics CSV must contain at least two distinct timestamps.")
    return (pd.Timestamp(ts[1]) - pd.Timestamp(ts[0])).total_seconds()


def _time_index(df: pd.DataFrame, start_real: float, interval_s: float) -> int:
    """Map elapsed real time → unique-timestamp index (wraps at end of CSV)."""
    elapsed_csv_s = (time.time() - start_real) * REPLAY_SPEED_X
    n = df["timestamp"].nunique()
    return int(elapsed_csv_s / interval_s) % n


def _push(df: pd.DataFrame, ts_index: int) -> None:
    """Write one time-slice into all Prometheus gauges."""
    ts_values = sorted(df["timestamp"].unique())
    current_ts = ts_values[ts_index]
    rrd_sim_ts.set(pd.Timestamp(current_ts).timestamp())

    slice_df = df[df["timestamp"] == current_ts]
    rrd_event._metrics.clear()

    for _, row in slice_df.iterrows():
        lv = [row["device_id"], row["port_id"], row["port_role"]]
        rrd_in_octets.labels(*lv).set(row["INOCTETS"])
        rrd_out_octets.labels(*lv).set(row["OUTOCTETS"])
        rrd_in_errors.labels(*lv).set(row["INERRORS"])
        rrd_out_errors.labels(*lv).set(row["OUTERRORS"])
        rrd_in_pkts.labels(*lv).set(row["INUCASTPKTS"])
        rrd_out_pkts.labels(*lv).set(row["OUTUCASTPKTS"])
        rrd_in_discards.labels(*lv).set(row["INDISCARDS"])
        rrd_out_discards.labels(*lv).set(row["OUTDISCARDS"])
        rrd_in_bcast.labels(*lv).set(row["INBROADCASTPKTS"])
        rrd_out_bcast.labels(*lv).set(row["OUTBROADCASTPKTS"])
        rrd_in_mcast.labels(*lv).set(row["INMULTICASTPKTS"])
        rrd_out_mcast.labels(*lv).set(row["OUTMULTICASTPKTS"])
        rrd_event.labels(*lv, row["event_label"]).set(1)


# ── Public API ────────────────────────────────────────────────────────────────

def run(csv_path: str = CSV_PATH, port: int = PORT) -> None:
    """Start the HTTP metrics server and loop forever."""
    df = _load(csv_path)
    interval_s = _interval_s(df)
    n_times = df["timestamp"].nunique()
    duration_h = n_times * interval_s / 3600
    cycle_min = (n_times * interval_s) / REPLAY_SPEED_X / 60

    print(f"[aiops-export] CSV: {csv_path}")
    print(f"  {len(df)} rows | {n_times} timestamps | {duration_h:.1f}h span")
    print(f"  Replay {REPLAY_SPEED_X}× → full cycle in ~{cycle_min:.0f} min real time")
    print(f"  Serving http://0.0.0.0:{port}/metrics")

    start_http_server(port)
    start_real = time.time()

    while True:
        idx = _time_index(df, start_real, interval_s)
        _push(df, idx)
        time.sleep(SCRAPE_INTERVAL)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
