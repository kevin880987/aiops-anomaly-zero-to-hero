#!/usr/bin/env python
"""Generate deterministic Lab05 alert-pipeline replay data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260810
SOURCE_CADENCE = pd.Timedelta(minutes=5)
ANOMALY_THRESHOLD = 3.0
SITE = "taipei-dc1"
TARGETS = ("fw01", "web01", "db01")
SCENARIOS = {
    "P1": (pd.Timestamp("2026-04-06 09:00:00"), 24),
    "P2": (pd.Timestamp("2026-04-07 09:00:00"), 36),
    "P3": (pd.Timestamp("2026-04-08 09:00:00"), 30),
    "P4": (pd.Timestamp("2026-04-09 09:00:00"), 36),
    "full_incident": (pd.Timestamp("2026-04-10 09:00:00"), 60),
}

METRIC_COLUMNS = (
    "scenario_id",
    "sample_index",
    "source_timestamp",
    "site",
    "target",
    "mahalanobis_score",
    "lof_score",
    "packet_loss_ratio",
    "service_up",
    "maintenance_active",
)

EVENT_COLUMNS = (
    "scenario_id",
    "event_id",
    "event_type",
    "target",
    "start_time",
    "end_time",
    "actionable",
    "root_cause_event_id",
    "maintenance",
    "expected_severity",
    "expected_receiver",
    "description",
)


def _event_time(scenario_id: str, index: int) -> pd.Timestamp:
    return SCENARIOS[scenario_id][0] + index * SOURCE_CADENCE


def _event(
    scenario_id: str,
    event_id: str,
    event_type: str,
    target: str,
    start_index: int,
    end_index: int,
    *,
    actionable: bool,
    severity: str,
    receiver: str,
    description: str,
    root_cause_event_id: str = "",
    maintenance: bool = False,
) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "event_id": event_id,
        "event_type": event_type,
        "target": target,
        "start_time": _event_time(scenario_id, start_index),
        "end_time": _event_time(scenario_id, end_index),
        "actionable": actionable,
        "root_cause_event_id": root_cause_event_id,
        "maintenance": maintenance,
        "expected_severity": severity,
        "expected_receiver": receiver,
        "description": description,
    }


def generate_event_catalog() -> pd.DataFrame:
    """Return source-time truth kept separate from replay measurements."""

    rows = [
        _event("P1", "P1-E1", "short_spike", "fw01", 5, 6,
               actionable=False, severity="none", receiver="none",
               description="單一取樣 spike，不值得通知人"),
        _event("P1", "P1-E2", "persistent_anomaly", "fw01", 9, 14,
               actionable=True, severity="warning", receiver="chat",
               description="持續超標，應通過 persistence gate"),
        _event("P1", "P1-E3", "threshold_flapping", "fw01", 16, 20,
               actionable=True, severity="warning", receiver="chat",
               description="門檻附近震盪，用來觀察狀態轉換"),
        _event("P2", "P2-E1", "multi_signal_incident", "fw01", 6, 30,
               actionable=True, severity="critical", receiver="pager",
               description="同一 incident 依序觸發 Mahalanobis、LOF 與 packet loss"),
        _event("P3", "P3-E1", "firewall_down", "fw01", 6, 24,
               actionable=True, severity="critical", receiver="pager",
               description="根因：防火牆停止服務"),
        _event("P3", "P3-E2", "web_down", "web01", 8, 24,
               actionable=True, severity="critical", receiver="suppressed",
               root_cause_event_id="P3-E1",
               description="下游症狀：Web 服務停止"),
        _event("P3", "P3-E3", "db_down", "db01", 10, 24,
               actionable=True, severity="critical", receiver="suppressed",
               root_cause_event_id="P3-E1",
               description="下游症狀：Database 服務停止"),
        _event("P4", "P4-E1", "warning_anomaly", "fw01", 5, 10,
               actionable=True, severity="warning", receiver="chat",
               description="一般時段 warning，送往 chat"),
        _event("P4", "P4-E2", "critical_packet_loss", "fw01", 12, 16,
               actionable=True, severity="critical", receiver="pager",
               description="一般時段 critical，送往 pager"),
        _event("P4", "P4-E3", "maintenance_anomaly", "fw01", 20, 27,
               actionable=False, severity="critical", receiver="suppressed",
               maintenance=True,
               description="維護期間 detector 仍觸發，但 notification 應被 Silence"),
        _event("full_incident", "F-E1", "short_spike", "fw01", 5, 6,
               actionable=False, severity="none", receiver="none",
               description="綜合案例的短暫 spike"),
        _event("full_incident", "F-E2", "persistent_anomaly", "fw01", 8, 17,
               actionable=True, severity="warning", receiver="chat",
               description="綜合案例的 persistence 與 flapping"),
        _event("full_incident", "F-E3", "multi_signal_incident", "fw01", 18, 32,
               actionable=True, severity="critical", receiver="pager",
               description="綜合案例的多 signal incident"),
        _event("full_incident", "F-E4", "firewall_down", "fw01", 34, 50,
               actionable=True, severity="critical", receiver="pager",
               description="綜合案例的防火牆根因"),
        _event("full_incident", "F-E5", "web_down", "web01", 36, 50,
               actionable=True, severity="critical", receiver="suppressed",
               root_cause_event_id="F-E4",
               description="綜合案例的 Web 症狀"),
        _event("full_incident", "F-E6", "db_down", "db01", 38, 50,
               actionable=True, severity="critical", receiver="suppressed",
               root_cause_event_id="F-E4",
               description="綜合案例的 Database 症狀"),
        _event("full_incident", "F-E7", "maintenance_anomaly", "fw01", 51, 56,
               actionable=False, severity="critical", receiver="suppressed",
               maintenance=True,
               description="綜合案例的維護時段異常"),
    ]
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _base_scenario(
    scenario_id: str,
    start: pd.Timestamp,
    points: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    target_offsets = {"fw01": 0.00, "web01": 0.08, "db01": -0.05}
    for sample_index in range(points):
        timestamp = start + sample_index * SOURCE_CADENCE
        for target in TARGETS:
            rows.append({
                "scenario_id": scenario_id,
                "sample_index": sample_index,
                "source_timestamp": timestamp,
                "site": SITE,
                "target": target,
                "mahalanobis_score": float(np.clip(rng.normal(1.0 + target_offsets[target], 0.10), 0.55, 1.45)),
                "lof_score": float(np.clip(rng.normal(1.04, 0.035), 0.90, 1.20)),
                "packet_loss_ratio": float(np.clip(rng.normal(0.001, 0.00012), 0.0005, 0.0015)),
                "service_up": 1,
                "maintenance_active": 0,
            })
    return pd.DataFrame(rows, columns=METRIC_COLUMNS)


def _set(frame: pd.DataFrame, scenario: str, target: str, indices, **values) -> None:
    if isinstance(indices, slice):
        start = 0 if indices.start is None else indices.start
        stop = int(frame.loc[frame["scenario_id"].eq(scenario), "sample_index"].max()) + 1 if indices.stop is None else indices.stop
        selected = range(start, stop)
    elif isinstance(indices, int):
        selected = [indices]
    else:
        selected = indices
    mask = (
        frame["scenario_id"].eq(scenario)
        & frame["target"].eq(target)
        & frame["sample_index"].isin(selected)
    )
    for column, value in values.items():
        if callable(value):
            frame.loc[mask, column] = value(frame.loc[mask, column])
        else:
            frame.loc[mask, column] = value


def _inject_p1(frame: pd.DataFrame) -> None:
    _set(frame, "P1", "fw01", 5, mahalanobis_score=4.8)
    _set(frame, "P1", "fw01", range(9, 14), mahalanobis_score=4.3)
    for index, value in zip(range(16, 20), (4.2, 2.7, 4.2, 2.7)):
        _set(frame, "P1", "fw01", index, mahalanobis_score=value)


def _inject_p2(frame: pd.DataFrame) -> None:
    _set(frame, "P2", "fw01", range(6, 30), mahalanobis_score=4.9)
    _set(frame, "P2", "fw01", range(8, 30), lof_score=2.4)
    _set(frame, "P2", "fw01", range(10, 30), packet_loss_ratio=0.04)


def _inject_p3(frame: pd.DataFrame) -> None:
    _set(frame, "P3", "fw01", range(6, 24), service_up=0, mahalanobis_score=5.2)
    _set(frame, "P3", "web01", range(8, 24), service_up=0, mahalanobis_score=4.6)
    _set(frame, "P3", "db01", range(10, 24), service_up=0, mahalanobis_score=4.7)


def _inject_p4(frame: pd.DataFrame) -> None:
    _set(frame, "P4", "fw01", range(5, 10), mahalanobis_score=4.4)
    _set(frame, "P4", "fw01", range(12, 16), packet_loss_ratio=0.05)
    _set(
        frame,
        "P4",
        "fw01",
        range(20, 27),
        mahalanobis_score=5.5,
        packet_loss_ratio=0.05,
        maintenance_active=1,
    )


def _inject_full(frame: pd.DataFrame) -> None:
    _set(frame, "full_incident", "fw01", 5, mahalanobis_score=4.8)
    _set(frame, "full_incident", "fw01", range(8, 12), mahalanobis_score=4.3)
    for index, value in zip(range(13, 17), (4.2, 2.7, 4.2, 2.7)):
        _set(frame, "full_incident", "fw01", index, mahalanobis_score=value)
    _set(frame, "full_incident", "fw01", range(18, 32), mahalanobis_score=5.0)
    _set(frame, "full_incident", "fw01", range(20, 32), lof_score=2.5)
    _set(frame, "full_incident", "fw01", range(22, 32), packet_loss_ratio=0.04)
    _set(frame, "full_incident", "fw01", range(34, 50), service_up=0, mahalanobis_score=5.4)
    _set(frame, "full_incident", "web01", range(36, 50), service_up=0, mahalanobis_score=4.7)
    _set(frame, "full_incident", "db01", range(38, 50), service_up=0, mahalanobis_score=4.8)
    _set(
        frame,
        "full_incident",
        "fw01",
        range(51, 56),
        mahalanobis_score=5.6,
        packet_loss_ratio=0.05,
        maintenance_active=1,
    )


def generate_replay_metrics(seed: int = SEED) -> pd.DataFrame:
    """Return all replay scenarios without event truth columns."""

    rng = np.random.default_rng(seed)
    frames = [
        _base_scenario(scenario_id, start, points, rng)
        for scenario_id, (start, points) in SCENARIOS.items()
    ]
    metrics = pd.concat(frames, ignore_index=True)
    _inject_p1(metrics)
    _inject_p2(metrics)
    _inject_p3(metrics)
    _inject_p4(metrics)
    _inject_full(metrics)
    return metrics.loc[:, METRIC_COLUMNS]


def generate_dataset(seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    return generate_replay_metrics(seed), generate_event_catalog()


def write_dataset(output_dir: Path | str = Path("data/synthetic")) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics, events = generate_dataset()
    metrics_path = output_dir / "lab05_replay_metrics.csv"
    events_path = output_dir / "lab05_event_catalog.csv"
    metrics.to_csv(metrics_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    events.to_csv(events_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    return metrics_path, events_path


if __name__ == "__main__":
    for path in write_dataset():
        print(path)
