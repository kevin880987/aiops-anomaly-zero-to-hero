"""
Synthetic RRD-like network metrics simulator (simulator_rrd_metrics.ipynb).

Generates 5-minute-resolution SNMP/RRD metrics for 5 ports across 3 devices,
including realistic daily/weekly seasonal patterns, random spikes, and a
catalogue of injected anomaly events.

Usage — library
---------------
>>> from aiops_monitor.simulator.rrd import generate
>>> metrics, events = generate(days=30, seed=42)
>>> metrics.to_csv("synthetic_rrd_metrics.csv", index=False)
>>> events.to_csv("synthetic_event_catalog.csv", index=False)

Usage — CLI (``aiops-simulate``)
---------------------------------
    aiops-simulate --days 30 --out-dir ./data/synthetic
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ── Port definitions ──────────────────────────────────────────────────────────
_PORTS = pd.DataFrame(
    [
        ("edge-fw-01",  "port-id7427", "wan-primary",    6.8e7, 0.72, 900,  0.95),
        ("edge-fw-01",  "port-id7428", "wan-secondary",  2.6e7, 0.55, 820,  0.70),
        ("core-sw-01",  "port-id7429", "server-uplink",  8.2e7, 0.38, 1050, 1.15),
        ("core-sw-01",  "port-id7430", "office-vlan",    3.4e7, 0.64, 760,  0.82),
        ("dist-sw-02",  "port-id7431", "backup-storage", 4.8e7, 0.44, 1180, 1.05),
    ],
    columns=["device_id", "port_id", "port_role",
             "base_octets", "in_share", "avg_packet_size", "business_weight"],
)


# ── Seasonal profiles ─────────────────────────────────────────────────────────

def _daily_profile(idx: pd.DatetimeIndex) -> np.ndarray:
    h = idx.hour + idx.minute / 60
    morning   = np.exp(-0.5 * ((h - 10.5) / 2.6) ** 2)
    afternoon = np.exp(-0.5 * ((h - 15.5) / 3.2) ** 2)
    evening   = 0.25 + 0.75 / (1 + np.exp(-(h - 7)))
    night     = 0.35 + 0.65 / (1 + np.exp(h - 21))
    return (0.45 + 0.40 * morning + 0.55 * afternoon) * evening * night


def _weekly_profile(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.where(idx.dayofweek >= 5, 0.58, 1.0)


def _random_spikes(n: int, rng: np.random.Generator,
                   probability: float = 0.006) -> np.ndarray:
    spikes = np.ones(n)
    for start in np.flatnonzero(rng.random(n) < probability):
        width = int(rng.integers(1, 5))
        spikes[start: start + width] *= float(rng.uniform(1.15, 1.75))
    return spikes


# ── Normal port series ────────────────────────────────────────────────────────

def _build_normal_series(port: pd.Series, timestamps: pd.DatetimeIndex,
                         rng: np.random.Generator) -> pd.DataFrame:
    n = len(timestamps)
    seasonal = _daily_profile(timestamps) * _weekly_profile(timestamps)
    noise    = rng.lognormal(mean=0.0, sigma=0.10, size=n)
    traffic  = (port.base_octets * port.business_weight
                * seasonal * noise * _random_spikes(n, rng))
    traffic  = np.maximum(traffic, port.base_octets * 0.04)

    asym      = np.clip(port.in_share + rng.normal(0, 0.035, n), 0.18, 0.86)
    in_oct    = traffic * asym
    out_oct   = traffic * (1 - asym)
    pkt_size  = np.clip(rng.normal(port.avg_packet_size,
                                   port.avg_packet_size * 0.08, n), 220, 1450)
    in_ucast  = in_oct  / pkt_size
    out_ucast = out_oct / pkt_size

    nucast_scale = rng.uniform(0.008, 0.018)
    bc_scale     = rng.uniform(0.0015, 0.004)
    mc_scale     = rng.uniform(0.003,  0.009)

    def _nucast(x): return np.maximum(x * nucast_scale, 1)
    def _bc(x):     return np.maximum(x * bc_scale, 0.2)
    def _mc(x):     return np.maximum(x * mc_scale, 0.5)

    return pd.DataFrame({
        "timestamp":       timestamps,
        "device_id":       port.device_id,
        "port_id":         port.port_id,
        "port_role":       port.port_role,
        "INOCTETS":        np.round(in_oct, 2),
        "OUTOCTETS":       np.round(out_oct, 2),
        "INERRORS":        np.zeros(n),
        "OUTERRORS":       np.zeros(n),
        "INUCASTPKTS":     np.round(in_ucast).astype(int),
        "OUTUCASTPKTS":    np.round(out_ucast).astype(int),
        "INNUCASTPKTS":    np.round(_nucast(in_ucast + out_ucast)).astype(int),
        "OUTNUCASTPKTS":   np.round(_nucast(in_ucast + out_ucast) * 0.9).astype(int),
        "INDISCARDS":      np.zeros(n),
        "OUTDISCARDS":     np.zeros(n),
        "INUNKNOWNPROTOS": np.zeros(n),
        "INBROADCASTPKTS":  np.round(_bc(in_ucast + out_ucast)).astype(int),
        "OUTBROADCASTPKTS": np.round(_bc(in_ucast + out_ucast) * 0.7).astype(int),
        "INMULTICASTPKTS":  np.round(_mc(in_ucast + out_ucast)).astype(int),
        "OUTMULTICASTPKTS": np.round(_mc(in_ucast + out_ucast) * 0.85).astype(int),
        "event_label": "normal",
        "event_id": pd.NA,
    })


# ── Anomaly event injection ───────────────────────────────────────────────────

_EVENT_TEMPLATES = [
    ("traffic_surge",    "port-id7427", dict(INOCTETS=3.5,  OUTOCTETS=2.8)),
    ("error_burst",      "port-id7428", dict(INERRORS=180,  OUTERRORS=90,   mode="add")),
    ("discard_spike",    "port-id7429", dict(INDISCARDS=45, OUTDISCARDS=30, mode="add")),
    ("traffic_drop",     "port-id7430", dict(INOCTETS=0.08, OUTOCTETS=0.08)),
    ("broadcast_storm",  "port-id7431", dict(INBROADCASTPKTS=12, OUTBROADCASTPKTS=10)),
]


# Packet-count columns stored as int — must stay int after mutation
_INT_COLS = {
    "INUCASTPKTS", "OUTUCASTPKTS", "INNUCASTPKTS", "OUTNUCASTPKTS",
    "INDISCARDS", "OUTDISCARDS", "INBROADCASTPKTS", "OUTBROADCASTPKTS",
    "INMULTICASTPKTS", "OUTMULTICASTPKTS", "INUNKNOWNPROTOS",
}


def _inject_events(df: pd.DataFrame, timestamps: pd.DatetimeIndex,
                   rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(timestamps)
    catalog: list[dict] = []
    df = df.copy()

    # Safe baseline/tail window: scale down for short simulations
    lo = min(7 * 24 * 12, n // 4)
    hi = max(lo + 1, n - min(2 * 24 * 12, n // 8))

    for eid, (label, port_id, mods) in enumerate(_EVENT_TEMPLATES, start=1):
        start_idx = int(rng.integers(lo, hi))
        dur_steps = int(rng.integers(6, min(36, hi - start_idx)))  # 30 min – 3 hrs

        mask = (df["port_id"] == port_id) & (
            df["timestamp"].isin(timestamps[start_idx: start_idx + dur_steps])
        )
        for col, factor in mods.items():
            if col == "mode":
                continue
            if mods.get("mode") == "add":
                new_vals = df.loc[mask, col] + factor * rng.uniform(0.8, 1.2, mask.sum())
            else:
                new_vals = df.loc[mask, col] * factor * rng.uniform(0.9, 1.1, mask.sum())

            if col in _INT_COLS:
                new_vals = new_vals.round().astype("int64")
            df.loc[mask, col] = new_vals

        df.loc[mask, "event_label"] = label
        df.loc[mask, "event_id"]    = f"E{eid:03d}"

        catalog.append({
            "event_id":   f"E{eid:03d}",
            "event_label": label,
            "port_id":     port_id,
            "start_time":  timestamps[start_idx],
            "end_time":    timestamps[min(start_idx + dur_steps, n - 1)],
            "duration_steps": dur_steps,
        })

    return df, pd.DataFrame(catalog)


# ── Public API ────────────────────────────────────────────────────────────────

def generate(
    start: str = "2026-02-01 00:00:00",
    days: int = 30,
    poll_seconds: int = 300,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic RRD-like network metrics.

    Parameters
    ----------
    start:       Simulation start timestamp (ISO string, default ``"2026-02-01"``).
    days:        Number of days to simulate (default 30).
    poll_seconds: SNMP polling interval in seconds (default 300 = 5 min).
    seed:        Random seed for reproducibility (default 42).

    Returns
    -------
    metrics : pd.DataFrame
        One row per (timestamp, port).  Columns match the real RRD CSV schema.
    events : pd.DataFrame
        Injected anomaly event catalogue with start/end timestamps.
    """
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start, periods=days * 24 * (3600 // poll_seconds),
                               freq=f"{poll_seconds}s")
    frames = [_build_normal_series(port, timestamps, rng)
              for _, port in _PORTS.iterrows()]
    df = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    df, events = _inject_events(df, timestamps, rng)
    return df, events


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic RRD metrics")
    parser.add_argument("--start",        default="2026-02-01 00:00:00")
    parser.add_argument("--days",   type=int, default=30)
    parser.add_argument("--poll",   type=int, default=300,
                        dest="poll_seconds", metavar="SECONDS")
    parser.add_argument("--seed",   type=int, default=42)
    parser.add_argument("--out-dir", default=".", metavar="DIR",
                        help="Directory to write synthetic_rrd_metrics.csv and synthetic_event_catalog.csv")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.days} days of metrics (seed={args.seed}) ...")
    metrics, events = generate(args.start, args.days, args.poll_seconds, args.seed)

    m_path = out / "synthetic_rrd_metrics.csv"
    e_path = out / "synthetic_event_catalog.csv"
    metrics.to_csv(m_path, index=False)
    events.to_csv(e_path, index=False)
    print(f"  {len(metrics):,} rows → {m_path}")
    print(f"  {len(events)} events → {e_path}")


if __name__ == "__main__":
    main()
