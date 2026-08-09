#!/usr/bin/env python
"""Lab04 multivariate geometry teaching-data generator.

The generator starts from latent traffic volume, packet size, and L2 packet
rates. Student-facing columns are derived from those drivers so their
cross-feature relationships remain physically interpretable.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

SEED = 20261004
CADENCE_MINUTES = 5
SLOTS_PER_DAY = 24 * 60 // CADENCE_MINUTES
ESTIMATE_DAYS = 42
CALIBRATION_DAYS = 14
REFERENCE_START = pd.Timestamp("2026-01-05 00:00:00")

DEVICE_ID = "core-sw-01"
PORT_ID = "port-id7429"
PORT_ROLE = "server-uplink"

FEATURES = (
    "in_bps",
    "out_bps",
    "in_pps",
    "out_pps",
    "avg_pkt_bytes",
    "broadcast_ratio",
    "multicast_ratio",
)
DATA_DIR = pathlib.Path(__file__).resolve().parent

# Common noise creates broad marginal variation; smaller direction-specific
# noise keeps the joint relationships informative.
NIGHT_MBPS = 75.0
DAY_MBPS = 285.0
WEEKEND_FACTOR = 0.66
OUT_RATIO = 0.56
BATCH_IN_ADD_MBPS = 145.0
BATCH_OUT_ADD_MBPS = 245.0
BATCH_PKT_IN_ADD = 80.0
BATCH_PKT_OUT_ADD = 180.0
PKT_IN_BYTES = 760.0
PKT_OUT_BYTES = 920.0


def _sigmoid(values: np.ndarray) -> np.ndarray:
    """Return a numerically stable logistic curve."""

    return 1.0 / (1.0 + np.exp(-np.clip(values, -50.0, 50.0)))


def _seasonal_level(index: pd.DatetimeIndex) -> np.ndarray:
    """Build the smooth weekday/weekend daily traffic level in Mbps."""

    hour = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    daytime = _sigmoid((hour - 7.2) / 0.7) - _sigmoid((hour - 20.0) / 0.8)
    weekday = NIGHT_MBPS + (DAY_MBPS - NIGHT_MBPS) * daytime
    return np.where(index.dayofweek.to_numpy() >= 5, weekday * WEEKEND_FACTOR, weekday)


def _batch_profile(
    index: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Draw one or two irregular two-to-four-hour batch windows per day."""

    active = np.zeros(len(index), dtype=bool)
    start_day = index[0].normalize()
    day_count = int((index[-1].normalize() - start_day).days) + 1
    window_count = 0
    for day_offset in range(day_count):
        count = int(rng.integers(1, 3))
        for _ in range(count):
            duration_hours = float(rng.uniform(2.0, 4.0))
            start_hour = float(rng.uniform(0.0, 24.0 - duration_hours))
            window_start = start_day + pd.Timedelta(days=day_offset, hours=start_hour)
            window_end = window_start + pd.Timedelta(hours=duration_hours)
            active |= (index >= window_start) & (index < window_end)
            window_count += 1
    return active, window_count


def _compose_features(drivers: pd.DataFrame) -> pd.DataFrame:
    """Convert latent traffic drivers into the seven monitoring features."""

    in_bps = drivers["in_mbps"].to_numpy() * 1e6
    out_bps = drivers["out_mbps"].to_numpy() * 1e6
    in_pps = (
        in_bps / (8.0 * drivers["pkt_in_bytes"].to_numpy())
        + drivers["pps_noise_in"].to_numpy()
    )
    out_pps = (
        out_bps / (8.0 * drivers["pkt_out_bytes"].to_numpy())
        + drivers["pps_noise_out"].to_numpy()
    )
    in_pps = np.clip(in_pps, 1.0, None)
    out_pps = np.clip(out_pps, 1.0, None)
    total_pps = in_pps + out_pps
    avg_pkt_bytes = (
        (in_bps + out_bps) / (8.0 * total_pps)
        + drivers["avg_pkt_noise"].to_numpy()
    )

    return pd.DataFrame(
        {
            "timestamp": pd.DatetimeIndex(drivers["timestamp"]),
            "in_bps": np.clip(in_bps, 0.0, None),
            "out_bps": np.clip(out_bps, 0.0, None),
            "in_pps": in_pps,
            "out_pps": out_pps,
            "avg_pkt_bytes": np.clip(avg_pkt_bytes, 64.0, 9000.0),
            "broadcast_ratio": np.clip(
                drivers["broadcast_pps"].to_numpy() / total_pps, 0.0, 1.0
            ),
            "multicast_ratio": np.clip(
                drivers["multicast_pps"].to_numpy() / total_pps, 0.0, 1.0
            ),
        }
    )


def _generate_reference_drivers(seed: int = SEED) -> pd.DataFrame:
    """Generate latent reference drivers, including private mode state."""

    seed_sequence = np.random.SeedSequence(seed)
    background_rng, batch_rng = [
        np.random.default_rng(child) for child in seed_sequence.spawn(2)
    ]
    days = ESTIMATE_DAYS + CALIBRATION_DAYS
    index = pd.date_range(
        REFERENCE_START,
        periods=days * SLOTS_PER_DAY,
        freq=f"{CADENCE_MINUTES}min",
    )
    seasonal = _seasonal_level(index)
    batch_active, batch_window_count = _batch_profile(index, batch_rng)
    if batch_window_count < 20:
        raise RuntimeError("fixed seed did not create enough normal batch windows")

    size = len(index)
    shared_volume_noise = background_rng.normal(0.0, 10.0, size)
    shared_packet_noise = background_rng.normal(0.0, 11.0, size)
    batch_float = batch_active.astype(float)
    in_mbps = (
        seasonal
        + shared_volume_noise
        + background_rng.normal(0.0, 2.5, size)
        + BATCH_IN_ADD_MBPS * batch_float
    )
    out_mbps = (
        OUT_RATIO * (seasonal + shared_volume_noise)
        + background_rng.normal(0.0, 2.0, size)
        + BATCH_OUT_ADD_MBPS * batch_float
    )
    pkt_in = (
        PKT_IN_BYTES
        + shared_packet_noise
        + background_rng.normal(0.0, 7.0, size)
        + BATCH_PKT_IN_ADD * batch_float
    )
    pkt_out = (
        PKT_OUT_BYTES
        + shared_packet_noise
        + background_rng.normal(0.0, 9.0, size)
        + BATCH_PKT_OUT_ADD * batch_float
    )

    seasonal_total_pps = (
        seasonal * 1e6 / (8.0 * PKT_IN_BYTES)
        + OUT_RATIO * seasonal * 1e6 / (8.0 * PKT_OUT_BYTES)
    )
    broadcast_pps = 0.017 * seasonal_total_pps * (
        1.0 + background_rng.normal(0.0, 0.025, size)
    )
    multicast_pps = 0.029 * seasonal_total_pps * (
        1.0 + background_rng.normal(0.0, 0.025, size)
    )

    split_boundary = REFERENCE_START + pd.Timedelta(days=ESTIMATE_DAYS)
    return pd.DataFrame(
        {
            "timestamp": index,
            "split": np.where(index < split_boundary, "estimate", "calibrate"),
            "batch_active": batch_active,
            "seasonal_mbps": seasonal,
            "in_mbps": np.clip(in_mbps, 1.0, None),
            "out_mbps": np.clip(out_mbps, 1.0, None),
            "pkt_in_bytes": np.clip(pkt_in, 128.0, None),
            "pkt_out_bytes": np.clip(pkt_out, 128.0, None),
            "pps_noise_in": background_rng.normal(0.0, 130.0, size),
            "pps_noise_out": background_rng.normal(0.0, 95.0, size),
            "avg_pkt_noise": background_rng.normal(0.0, 20.0, size),
            "broadcast_pps": np.clip(broadcast_pps, 0.0, None),
            "multicast_pps": np.clip(multicast_pps, 0.0, None),
        }
    )


def generate_reference(seed: int = SEED) -> pd.DataFrame:
    """Return deterministic, student-facing normal reference observations."""

    drivers = _generate_reference_drivers(seed)
    features = _compose_features(drivers)
    features.insert(1, "split", drivers["split"].to_numpy())
    features.insert(2, "device_id", DEVICE_ID)
    features.insert(3, "port_id", PORT_ID)
    features.insert(4, "port_role", PORT_ROLE)
    return features.loc[
        :, ["timestamp", "split", "device_id", "port_id", "port_role", *FEATURES]
    ]
