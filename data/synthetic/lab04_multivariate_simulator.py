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
SCENARIO_START = pd.Timestamp("2026-03-02 00:00:00")
SCENARIO_DAYS = 3
EVENT_START = SCENARIO_START + pd.Timedelta(days=1, hours=9)
EVENT_END = SCENARIO_START + pd.Timedelta(days=1, hours=15)

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


def _time_features(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Return weekday/weekend type and the five-minute slot of day."""

    day_type = np.where(index.dayofweek.to_numpy() >= 5, "weekend", "weekday")
    slot = (index.hour.to_numpy() * 60 + index.minute.to_numpy()) // CADENCE_MINUTES
    return day_type, slot


def fit_seasonal_profiles(
    frame: pd.DataFrame,
    features: tuple[str, ...] = FEATURES,
    radius: int = 6,
) -> dict[str, pd.DataFrame]:
    """Fit Lab03-compatible weekday/weekend profiles on estimate rows."""

    if radius < 0:
        raise ValueError("radius must be nonnegative")
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise ValueError(f"missing feature columns: {missing}")
    index = pd.DatetimeIndex(frame["timestamp"])
    day_type, slot = _time_features(index)
    work = frame.loc[:, features].copy()
    work["day_type"] = day_type
    work["slot"] = slot
    profiles: dict[str, pd.DataFrame] = {}
    for kind in ("weekday", "weekend"):
        raw = (
            work.loc[work["day_type"] == kind]
            .groupby("slot")[list(features)]
            .mean()
            .reindex(range(SLOTS_PER_DAY))
            .interpolate(limit_direction="both")
        )
        shifted = [np.roll(raw.to_numpy(), shift, axis=0) for shift in range(-radius, radius + 1)]
        profiles[kind] = pd.DataFrame(
            np.mean(np.stack(shifted), axis=0),
            index=pd.RangeIndex(SLOTS_PER_DAY, name="slot"),
            columns=features,
        )
    return profiles


def apply_seasonal_profiles(
    frame: pd.DataFrame,
    profiles: dict[str, pd.DataFrame],
    features: tuple[str, ...] = FEATURES,
) -> pd.DataFrame:
    """Apply frozen weekday/weekend profiles to arbitrary timestamps."""

    index = pd.DatetimeIndex(frame["timestamp"])
    day_type, slot = _time_features(index)
    values = np.vstack(
        [profiles[kind].iloc[position].to_numpy() for kind, position in zip(day_type, slot)]
    )
    return pd.DataFrame(values, index=frame.index, columns=features)


def _generate_story_drivers(seed: int) -> pd.DataFrame:
    """Build one shared three-day monitoring background."""

    seed_sequence = np.random.SeedSequence(seed)
    background_rng, batch_rng = [
        np.random.default_rng(child) for child in seed_sequence.spawn(2)
    ]
    index = pd.date_range(
        SCENARIO_START,
        periods=SCENARIO_DAYS * SLOTS_PER_DAY,
        freq=f"{CADENCE_MINUTES}min",
    )
    seasonal = _seasonal_level(index)
    batch_active, _ = _batch_profile(index, batch_rng)
    size = len(index)
    common_volume = background_rng.normal(0.0, 10.0, size)
    common_packet = background_rng.normal(0.0, 11.0, size)
    batch_float = batch_active.astype(float)
    seasonal_total_pps = (
        seasonal * 1e6 / (8.0 * PKT_IN_BYTES)
        + OUT_RATIO * seasonal * 1e6 / (8.0 * PKT_OUT_BYTES)
    )
    return pd.DataFrame(
        {
            "timestamp": index,
            "batch_active": batch_active,
            "seasonal_mbps": seasonal,
            "in_mbps": np.clip(
                seasonal
                + common_volume
                + background_rng.normal(0.0, 2.5, size)
                + BATCH_IN_ADD_MBPS * batch_float,
                1.0,
                None,
            ),
            "out_mbps": np.clip(
                OUT_RATIO * (seasonal + common_volume)
                + background_rng.normal(0.0, 2.0, size)
                + BATCH_OUT_ADD_MBPS * batch_float,
                1.0,
                None,
            ),
            "pkt_in_bytes": np.clip(
                PKT_IN_BYTES
                + common_packet
                + background_rng.normal(0.0, 7.0, size)
                + BATCH_PKT_IN_ADD * batch_float,
                128.0,
                None,
            ),
            "pkt_out_bytes": np.clip(
                PKT_OUT_BYTES
                + common_packet
                + background_rng.normal(0.0, 9.0, size)
                + BATCH_PKT_OUT_ADD * batch_float,
                128.0,
                None,
            ),
            "pps_noise_in": background_rng.normal(0.0, 130.0, size),
            "pps_noise_out": background_rng.normal(0.0, 95.0, size),
            "avg_pkt_noise": background_rng.normal(0.0, 20.0, size),
            "broadcast_pps": np.clip(
                0.017
                * seasonal_total_pps
                * (1.0 + background_rng.normal(0.0, 0.025, size)),
                0.0,
                None,
            ),
            "multicast_pps": np.clip(
                0.029
                * seasonal_total_pps
                * (1.0 + background_rng.normal(0.0, 0.025, size)),
                0.0,
                None,
            ),
        }
    )


def _remove_batch_effect(drivers: pd.DataFrame, mask: np.ndarray) -> None:
    """Put an event window into the ordinary normal mode before injection."""

    active = mask & drivers["batch_active"].to_numpy()
    drivers.loc[active, "in_mbps"] -= BATCH_IN_ADD_MBPS
    drivers.loc[active, "out_mbps"] -= BATCH_OUT_ADD_MBPS
    drivers.loc[active, "pkt_in_bytes"] -= BATCH_PKT_IN_ADD
    drivers.loc[active, "pkt_out_bytes"] -= BATCH_PKT_OUT_ADD
    drivers.loc[mask, "batch_active"] = False


def inject_m1_correlation_break(drivers: pd.DataFrame, mask: np.ndarray) -> None:
    """Create a physical small-packet correlation break."""

    _remove_batch_effect(drivers, mask)
    drivers.loc[mask, "pkt_in_bytes"] *= 0.94


def inject_m2_density_valley(drivers: pd.DataFrame, mask: np.ndarray) -> None:
    """Place latent traffic halfway between ordinary and batch modes."""

    _remove_batch_effect(drivers, mask)
    drivers.loc[mask, "in_mbps"] += 0.50 * BATCH_IN_ADD_MBPS
    drivers.loc[mask, "out_mbps"] += 0.50 * BATCH_OUT_ADD_MBPS
    drivers.loc[mask, "pkt_in_bytes"] += 0.50 * BATCH_PKT_IN_ADD
    drivers.loc[mask, "pkt_out_bytes"] += 0.50 * BATCH_PKT_OUT_ADD


def inject_m3_off_subspace(drivers: pd.DataFrame, mask: np.ndarray) -> None:
    """Change L2 composition while holding total traffic fixed."""

    _remove_batch_effect(drivers, mask)
    drivers.loc[mask, "broadcast_pps"] *= 1.57
    drivers.loc[mask, "multicast_pps"] *= 0.56


def inject_m4_along_subspace(drivers: pd.DataFrame, mask: np.ndarray) -> None:
    """Move beyond normal activity along the shared traffic-volume direction."""

    _remove_batch_effect(drivers, mask)
    seasonal = drivers.loc[mask, "seasonal_mbps"]
    drivers.loc[mask, "in_mbps"] = (
        seasonal
        + 0.5 * (drivers.loc[mask, "in_mbps"] - seasonal)
        + 1.36 * BATCH_IN_ADD_MBPS
    )
    drivers.loc[mask, "out_mbps"] = (
        OUT_RATIO * seasonal
        + 0.5 * (drivers.loc[mask, "out_mbps"] - OUT_RATIO * seasonal)
        + 1.36 * BATCH_OUT_ADD_MBPS
    )
    drivers.loc[mask, "pkt_in_bytes"] = (
        PKT_IN_BYTES
        + 0.5 * (drivers.loc[mask, "pkt_in_bytes"] - PKT_IN_BYTES)
        + 1.36 * BATCH_PKT_IN_ADD
    )
    drivers.loc[mask, "pkt_out_bytes"] = (
        PKT_OUT_BYTES
        + 0.5 * (drivers.loc[mask, "pkt_out_bytes"] - PKT_OUT_BYTES)
        + 1.36 * BATCH_PKT_OUT_ADD
    )
    drivers.loc[mask, "pps_noise_in"] *= 0.5
    drivers.loc[mask, "pps_noise_out"] *= 0.5
    drivers.loc[mask, "avg_pkt_noise"] *= 0.5


def _student_scenario_frame(scenario_id: str, drivers: pd.DataFrame) -> pd.DataFrame:
    """Compose a scenario and attach only non-truth metadata."""

    features = _compose_features(drivers)
    features.insert(0, "scenario_id", scenario_id)
    features.insert(2, "device_id", DEVICE_ID)
    features.insert(3, "port_id", PORT_ID)
    features.insert(4, "port_role", PORT_ROLE)
    return features.loc[
        :, ["scenario_id", "timestamp", "device_id", "port_id", "port_role", *FEATURES]
    ]


def generate_dataset(
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return reference, four geometry scenarios, and separate event truth."""

    reference = generate_reference(seed)
    base = _generate_story_drivers(seed + 1_000)
    mask = base["timestamp"].ge(EVENT_START) & base["timestamp"].lt(EVENT_END)
    injectors = {
        "M1": inject_m1_correlation_break,
        "M2": inject_m2_density_valley,
        "M3": inject_m3_off_subspace,
        "M4": inject_m4_along_subspace,
    }
    parts = []
    for scenario_id, injector in injectors.items():
        drivers = base.copy(deep=True)
        injector(drivers, mask.to_numpy())
        parts.append(_student_scenario_frame(scenario_id, drivers))
    scenarios = pd.concat(parts, ignore_index=True)

    event_types = {
        "M1": ("small_packet_scan", "小封包掃描破壞 throughput 與 packet-rate 關係"),
        "M2": ("off_mode_traffic_mix", "流量落在 ordinary 與 batch normal modes 的低密度中間"),
        "M3": ("l2_composition_mismatch", "總流量不變但 broadcast/multicast composition 偏離 normal subspace"),
        "M4": ("coordinated_bulk_extreme", "feature relationships 正常但沿主要 traffic direction 超出 operating envelope"),
    }
    events = pd.DataFrame(
        [
            {
                "scenario_id": scenario_id,
                "event_id": f"{scenario_id}-E1",
                "event_type": event_types[scenario_id][0],
                "start_time": EVENT_START,
                "end_time": EVENT_END,
                "description": event_types[scenario_id][1],
            }
            for scenario_id in injectors
        ]
    )
    return reference, scenarios, events


def write_dataset(
    output_dir: pathlib.Path = DATA_DIR,
    seed: int = SEED,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Write the three canonical CSV files and return their paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    reference, scenarios, events = generate_dataset(seed)
    paths = (
        output_dir / "lab04_reference.csv",
        output_dir / "lab04_multivariate_scenarios.csv",
        output_dir / "lab04_multivariate_events.csv",
    )
    reference.to_csv(paths[0], index=False, date_format="%Y-%m-%d %H:%M:%S")
    scenarios.to_csv(paths[1], index=False, date_format="%Y-%m-%d %H:%M:%S")
    events.to_csv(paths[2], index=False, date_format="%Y-%m-%d %H:%M:%S")
    return paths


if __name__ == "__main__":
    for written_path in write_dataset():
        print(written_path)
