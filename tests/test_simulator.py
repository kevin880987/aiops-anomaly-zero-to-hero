"""Tests for aiops_monitor.simulator.rrd"""
import pandas as pd
import pytest
from aiops_monitor.simulator.rrd import generate


def test_generate_shape():
    metrics, events = generate(days=3, seed=0)
    # 3 days × 24h × 12 intervals × 5 ports
    assert len(metrics) == 3 * 24 * 12 * 5
    assert set(metrics.columns) >= {
        "timestamp", "device_id", "port_id", "INOCTETS", "OUTOCTETS",
        "INERRORS", "OUTERRORS", "event_label",
    }


def test_generate_event_catalog():
    _, events = generate(days=14, seed=1)
    assert len(events) == 5  # one event per template
    assert set(events.columns) >= {"event_id", "event_label", "port_id", "start_time", "end_time"}


def test_generate_reproducible():
    m1, _ = generate(days=3, seed=42)
    m2, _ = generate(days=3, seed=42)
    pd.testing.assert_frame_equal(m1, m2)


def test_generate_different_seeds():
    m1, _ = generate(days=3, seed=0)
    m2, _ = generate(days=3, seed=99)
    assert not m1["INOCTETS"].equals(m2["INOCTETS"])


def test_anomaly_rows_present():
    metrics, events = generate(days=14, seed=42)
    assert (metrics["event_label"] != "normal").any()
