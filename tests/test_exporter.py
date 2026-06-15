from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from aiops_monitor.exporter import metrics_exporter


@pytest.fixture
def metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-02-01 00:00:00",
                    "2026-02-01 00:05:00",
                    "2026-02-01 00:10:00",
                ]
            ),
            "event_label": ["normal", "normal", "error_burst"],
        }
    )


def test_interval_is_inferred_from_distinct_timestamps(metrics: pd.DataFrame) -> None:
    assert metrics_exporter._interval_s(metrics) == 300


def test_interval_requires_two_timestamps() -> None:
    one_timestamp = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-02-01 00:00:00"]),
            "event_label": ["normal"],
        }
    )

    with pytest.raises(ValueError, match="at least two distinct timestamps"):
        metrics_exporter._interval_s(one_timestamp)


def test_replay_speed_is_a_conventional_multiplier(metrics: pd.DataFrame) -> None:
    with (
        mock.patch.object(metrics_exporter, "REPLAY_SPEED_X", 60),
        mock.patch.object(metrics_exporter.time, "time", return_value=105.0),
    ):
        index = metrics_exporter._time_index(
            metrics,
            start_real=100.0,
            interval_s=300.0,
        )

    assert index == 1
