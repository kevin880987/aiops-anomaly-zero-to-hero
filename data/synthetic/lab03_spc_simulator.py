#!/usr/bin/env python
"""產生 Lab03 temporal-pattern 教學資料。

輸出三個 CSV：reference、S1–S3 monitoring series，以及獨立事件真值。
所有隨機來源均由顯式 seed 控制；相同 seed 必須產生逐列相同的資料。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260809
DATA_DIR = Path(__file__).resolve().parent

DEVICE_ID = "sw-core-01"
PORT_ID = "port-id7430"
PORT_ROLE = "uplink"

CADENCE_MINUTES = 5
SLOTS_PER_DAY = 24 * 60 // CADENCE_MINUTES

REFERENCE_START = pd.Timestamp("2026-01-19 00:00")
ESTIMATE_DAYS = 28
CALIBRATION_DAYS = 14
REFERENCE_DAYS = ESTIMATE_DAYS + CALIBRATION_DAYS

MONITORING_START = pd.Timestamp("2026-03-02 00:00")
MONITORING_DAYS = 7

NIGHT_LEVEL = 15.0
DAY_LEVEL = 45.0
WEEKEND_FACTOR = 0.60
NOISE_STD = 3.0

MORNING_CENTER_HOUR = 7.0
MORNING_WIDTH_HOUR = 0.6
EVENING_CENTER_HOUR = 19.5
EVENING_WIDTH_HOUR = 0.6

S1_AMPLITUDE_SIGMA = 4.5
S2_AMPLITUDE_SIGMA = 0.8
S3_FINAL_AMPLITUDE_SIGMA = 2.5
S1_EVENT_TIMES = (
    pd.Timestamp("2026-03-04 10:00"),
    pd.Timestamp("2026-03-06 14:00"),
    pd.Timestamp("2026-03-08 10:00"),
)

REFERENCE_COLUMNS = [
    "timestamp",
    "split",
    "device_id",
    "port_id",
    "port_role",
    "utilization",
]
SCENARIO_COLUMNS = [
    "scenario_id",
    "timestamp",
    "device_id",
    "port_id",
    "port_role",
    "utilization",
]
EVENT_COLUMNS = [
    "scenario_id",
    "event_id",
    "event_type",
    "start_time",
    "end_time",
    "description",
]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    """回傳數值穩定的 logistic transition。"""

    return 1.0 / (1.0 + np.exp(-np.clip(values, -50.0, 50.0)))


def seasonal_level(index: pd.DatetimeIndex) -> np.ndarray:
    """建立平滑 daily 與 weekday/weekend seasonal baseline。"""

    hour = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    morning = _sigmoid(
        (hour - MORNING_CENTER_HOUR) / MORNING_WIDTH_HOUR
    )
    evening = _sigmoid(
        (hour - EVENING_CENTER_HOUR) / EVENING_WIDTH_HOUR
    )
    daily_shape = morning - evening
    weekday_level = NIGHT_LEVEL + (DAY_LEVEL - NIGHT_LEVEL) * daily_shape
    weekend = index.dayofweek.to_numpy() >= 5
    return np.where(weekend, weekday_level * WEEKEND_FACTOR, weekday_level)


def _time_features(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """將 timestamp 轉成 day type 與五分鐘 slot。"""

    day_type = np.where(index.dayofweek.to_numpy() >= 5, "weekend", "weekday")
    slot = (
        index.hour.to_numpy() * 60 + index.minute.to_numpy()
    ) // CADENCE_MINUTES
    return day_type, slot


def _smooth_circular(values: np.ndarray, radius: int = 6) -> np.ndarray:
    """以環狀 moving average 平滑一天的 seasonal profile。"""

    shifted = [
        np.roll(values, shift)
        for shift in range(-radius, radius + 1)
    ]
    return np.mean(np.stack(shifted), axis=0)


def fit_seasonal_profile(reference_estimate: pd.DataFrame) -> dict[str, np.ndarray]:
    """只用 estimate rows 建立 weekday／weekend time-of-day profile。"""

    index = pd.DatetimeIndex(reference_estimate["timestamp"])
    day_type, slot = _time_features(index)
    work = pd.DataFrame(
        {
            "day_type": day_type,
            "slot": slot,
            "utilization": reference_estimate["utilization"].to_numpy(),
        }
    )
    profiles: dict[str, np.ndarray] = {}
    for kind in ("weekday", "weekend"):
        raw = (
            work.loc[work["day_type"] == kind]
            .groupby("slot")["utilization"]
            .mean()
            .reindex(range(SLOTS_PER_DAY))
            .interpolate(limit_direction="both")
            .to_numpy()
        )
        profiles[kind] = _smooth_circular(raw)
    return profiles


def apply_seasonal_profile(
    frame: pd.DataFrame,
    profiles: dict[str, np.ndarray],
) -> np.ndarray:
    """將已凍結的 seasonal profile 套用至任意時間軸。"""

    index = pd.DatetimeIndex(frame["timestamp"])
    day_type, slot = _time_features(index)
    return np.array(
        [profiles[kind][position] for kind, position in zip(day_type, slot)],
        dtype=float,
    )


def estimate_sigma_mr(reference_estimate: pd.DataFrame) -> float:
    """以 estimate residual 的 MR-bar / 1.128 估計 individual scale。"""

    profiles = fit_seasonal_profile(reference_estimate)
    baseline = apply_seasonal_profile(reference_estimate, profiles)
    residual = reference_estimate["utilization"].to_numpy() - baseline
    moving_range = np.abs(np.diff(residual))
    return float(moving_range.mean() / 1.128)


def _base_frame(index: pd.DatetimeIndex, utilization: np.ndarray) -> pd.DataFrame:
    """加入單一 monitored entity 的 metadata。"""

    return pd.DataFrame(
        {
            "timestamp": index,
            "device_id": DEVICE_ID,
            "port_id": PORT_ID,
            "port_role": PORT_ROLE,
            "utilization": np.clip(utilization, 0.0, 100.0),
        }
    )


def _generate_reference(rng: np.random.Generator) -> pd.DataFrame:
    """產生六個完整星期的 clean Phase I reference。"""

    index = pd.date_range(
        start=REFERENCE_START,
        periods=REFERENCE_DAYS * SLOTS_PER_DAY,
        freq=f"{CADENCE_MINUTES}min",
    )
    utilization = seasonal_level(index) + rng.normal(0.0, NOISE_STD, len(index))
    reference = _base_frame(index, utilization)
    split_boundary = REFERENCE_START + pd.Timedelta(days=ESTIMATE_DAYS)
    reference.insert(
        1,
        "split",
        np.where(reference["timestamp"] < split_boundary, "estimate", "calibrate"),
    )
    return reference.loc[:, REFERENCE_COLUMNS]


def _generate_monitoring_background(rng: np.random.Generator) -> pd.DataFrame:
    """產生供 S1–S3 複製的同一段七天正常背景。"""

    index = pd.date_range(
        start=MONITORING_START,
        periods=MONITORING_DAYS * SLOTS_PER_DAY,
        freq=f"{CADENCE_MINUTES}min",
    )
    utilization = seasonal_level(index) + rng.normal(0.0, NOISE_STD, len(index))
    return _base_frame(index, utilization)


def _scenario_frame(
    scenario_id: str,
    background: pd.DataFrame,
) -> pd.DataFrame:
    """複製背景並加入 scenario ID。"""

    frame = background.copy()
    frame.insert(0, "scenario_id", scenario_id)
    return frame.loc[:, SCENARIO_COLUMNS]


def _generate_scenarios(
    background: pd.DataFrame,
    sigma_mr: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """注入三種 temporal pattern 並建立獨立事件表。"""

    scenario_frames: list[pd.DataFrame] = []
    event_rows: list[dict[str, object]] = []

    s1 = _scenario_frame("S1", background)
    for event_number, event_time in enumerate(S1_EVENT_TIMES, start=1):
        s1.loc[s1["timestamp"] == event_time, "utilization"] += (
            S1_AMPLITUDE_SIGMA * sigma_mr
        )
        event_rows.append(
            {
                "scenario_id": "S1",
                "event_id": f"S1-E{event_number}",
                "event_type": "large_spike",
                "start_time": event_time,
                "end_time": event_time,
                "description": (
                    "單一五分鐘 large spike；三次事件彼此分離，測試即時極端值偵測。"
                ),
            }
        )
    scenario_frames.append(s1)

    s2 = _scenario_frame("S2", background)
    s2_start = pd.Timestamp("2026-03-04 09:00")
    s2_stop = s2_start + pd.Timedelta(hours=36)
    s2_mask = (s2["timestamp"] >= s2_start) & (s2["timestamp"] < s2_stop)
    s2.loc[s2_mask, "utilization"] += S2_AMPLITUDE_SIGMA * sigma_mr
    scenario_frames.append(s2)
    event_rows.append(
        {
            "scenario_id": "S2",
            "event_id": "S2-E1",
            "event_type": "small_persistent_shift",
            "start_time": s2_start,
            "end_time": s2_stop - pd.Timedelta(minutes=CADENCE_MINUTES),
            "description": "持續 36 小時的小幅位移，測試跨時間累積證據。",
        }
    )

    s3 = _scenario_frame("S3", background)
    s3_start = pd.Timestamp("2026-03-04 00:00")
    ramp_duration = pd.Timedelta(hours=72)
    elapsed = (
        s3["timestamp"] - s3_start
    ).dt.total_seconds().to_numpy() / ramp_duration.total_seconds()
    ramp_fraction = np.clip(elapsed, 0.0, 1.0)
    active = s3["timestamp"] >= s3_start
    s3.loc[active, "utilization"] += (
        ramp_fraction[active.to_numpy()]
        * S3_FINAL_AMPLITUDE_SIGMA
        * sigma_mr
    )
    scenario_frames.append(s3)
    event_rows.append(
        {
            "scenario_id": "S3",
            "event_id": "S3-E1",
            "event_type": "gradual_drift",
            "start_time": s3_start,
            "end_time": s3["timestamp"].iloc[-1],
            "description": "72 小時 gradual drift 至新水準，之後維持到視窗結束。",
        }
    )

    scenarios = pd.concat(scenario_frames, ignore_index=True)
    scenarios["utilization"] = scenarios["utilization"].clip(0.0, 100.0)
    events = pd.DataFrame(event_rows, columns=EVENT_COLUMNS)
    return scenarios.loc[:, SCENARIO_COLUMNS], events


def generate_dataset(
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """回傳 reference、scenarios 與 events 三個 deterministic tables。"""

    reference_rng = np.random.default_rng(seed)
    monitoring_rng = np.random.default_rng(seed + 1)
    reference = _generate_reference(reference_rng)
    estimate = reference.loc[reference["split"] == "estimate"].copy()
    sigma_mr = estimate_sigma_mr(estimate)
    background = _generate_monitoring_background(monitoring_rng)
    scenarios, events = _generate_scenarios(background, sigma_mr)
    return reference, scenarios, events


def write_dataset(
    output_dir: Path = DATA_DIR,
    seed: int = SEED,
) -> tuple[Path, Path, Path]:
    """將三個 canonical CSV 寫入指定目錄並回傳路徑。"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reference, scenarios, events = generate_dataset(seed)
    paths = (
        output_dir / "lab03_reference.csv",
        output_dir / "lab03_spc_scenarios.csv",
        output_dir / "lab03_spc_events.csv",
    )
    for frame, path in zip((reference, scenarios, events), paths):
        frame.to_csv(
            path,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
            float_format="%.6f",
        )
    return paths


if __name__ == "__main__":
    for written_path in write_dataset():
        print(written_path)
