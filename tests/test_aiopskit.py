"""Regression tests for the workshop library.

These pin the properties that, when they broke silently during development, made
every downstream number in the labs wrong: the counter-versus-delta reading, the
sampling cadence, and the scale floor used by every deviation score.

    pytest tests/test_aiopskit.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "infra"))

import aiopskit as wk  # noqa: E402
from aiopskit import baselines, data, detect, evaluate, viz  # noqa: E402


@pytest.fixture(scope="module")
def telemetry():
    frame, contract = wk.load_telemetry()
    return frame, contract


# ---------------------------------------------------------------------------
# The unit contract
# ---------------------------------------------------------------------------

def test_cadence_is_five_minutes(telemetry):
    """Labs quote window lengths in minutes; a wrong cadence makes all of them wrong."""
    _, contract = telemetry
    assert contract.cadence_s == 300.0


def test_columns_are_read_as_deltas_not_counters(telemetry):
    """INOCTETS falls as often as it rises, so differencing it destroys half the data."""
    _, contract = telemetry
    assert contract.semantics == "delta"
    assert 0.45 < contract.monotonic_fraction < 0.6


def test_counter_reading_would_have_destroyed_the_signal():
    """Guards the specific defect this loader was written to prevent."""
    as_delta, _ = wk.load_telemetry(ports=["port-id7429"], semantics="delta")
    as_counter, _ = wk.load_telemetry(ports=["port-id7429"], semantics="counter")
    zeros = (as_counter["inoctets_ps"] == 0).mean()
    assert zeros > 0.4, "counter reading should clip roughly half the samples to zero"
    assert as_delta["inoctets_ps"].mean() > 5 * as_counter["inoctets_ps"].mean()


def test_derived_rates_are_finite_and_non_negative(telemetry):
    frame, _ = telemetry
    for column in ["traffic_bps", "packets_pps", "error_rate", "broadcast_ratio", "avg_pkt_bytes"]:
        values = frame[column]
        assert np.isfinite(values).all(), f"{column} has non-finite values"
        assert (values >= 0).all(), f"{column} has negative values"
    assert frame["tx_ratio"].between(0, 1).all()


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def test_events_expand_per_port(telemetry):
    """G and H hit every port, which is what makes the peer baseline blind to them."""
    frame, _ = telemetry
    events = wk.load_events(frame)
    assert len(events) == 18
    for event_id in ("G", "H"):
        assert (events["event_id"] == event_id).sum() == 5


def test_change_calendar_splits_incidents_from_planned(telemetry):
    frame, _ = telemetry
    events = wk.load_events(frame)
    incidents, planned = wk.split_events(events, wk.load_change_calendar())
    assert len(incidents) == 16
    assert set(planned["event_id"]) == {"A", "C"}
    assert set(planned["change_id"]) == {"CH-01", "CH-02"}


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def test_scale_floor_is_derived_from_spread_not_level():
    """A metric centred far from zero must not be floored at its own level.

    This was a live defect: flooring on the magnitude quantile capped the score
    of avg_pkt_bytes at 2.3 sigma and hid every packet-size anomaly.
    """
    offset = pd.Series(1000 + np.random.default_rng(0).normal(0, 5, 2000))
    centred = pd.Series(np.random.default_rng(0).normal(0, 5, 2000))
    assert baselines.scale_floor(offset) == pytest.approx(baselines.scale_floor(centred), rel=0.3)
    assert baselines.scale_floor(offset) < 5


def test_scale_floor_survives_an_all_zero_series():
    assert baselines.scale_floor(pd.Series(np.zeros(500))) > 0


def test_degenerate_fraction_flags_a_near_constant_metric(telemetry):
    """error_rate is zero almost always, so a z-score against it is not a measurement."""
    frame, contract = telemetry
    port = wk.single_port(frame, "port-id7429")
    window = int(3600 / contract.cadence_s)

    _, quiet_scale = baselines.rolling_robust(port["error_rate"], window)
    _, busy_scale = baselines.rolling_robust(port["traffic_bps"], window)
    assert baselines.degenerate_fraction(quiet_scale, port["error_rate"]) > 0.9
    assert baselines.degenerate_fraction(busy_scale, port["traffic_bps"]) < 0.5


def test_deviation_score_is_capped():
    values = pd.Series([0.0] * 100 + [1e9])
    center, scale = baselines.rolling_robust(values, 10)
    score = baselines.deviation_score(values, center, scale)
    assert score.abs().max() <= baselines.MAX_SCORE


def test_peer_baseline_leaves_the_port_itself_out(telemetry):
    """Otherwise a port contributes to the median it is being judged against."""
    frame, _ = telemetry
    center, scale = baselines.peer(frame, "traffic_bps")
    assert len(center) == len(frame)
    assert center.notna().all() and (scale > 0).all()

    sub = frame[frame["timestamp"] == frame["timestamp"].iloc[0]]
    others = sub[sub["port_id"] != sub["port_id"].iloc[0]]["traffic_bps"]
    assert center.loc[sub.index[0]] == pytest.approx(float(others.median()))


def test_seasonal_baseline_can_exclude_known_incidents(telemetry):
    frame, _ = telemetry
    port = wk.single_port(frame, "port-id7431")
    events = wk.load_events(frame)
    clean = ~wk.truth_mask(port, events)

    _, contaminated = baselines.seasonal(port, "traffic_bps")
    _, excluded = baselines.seasonal(port, "traffic_bps", train_mask=clean)
    assert len(excluded) == len(port)
    assert excluded.median() <= contaminated.median() * 1.05


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_confirm_separates_breach_from_label():
    """The label lags the breach by the confirmation window; that lag is the price."""
    score = pd.Series([0, 9, 0, 9, 9, 9, 0])
    flags = detect.confirm(score, threshold=1.0, n_consecutive=3)
    assert flags["breach"].sum() == 4
    assert not flags["label"].iloc[1], "an isolated breach must not become a label"
    assert not flags["label"].iloc[4], "two of three is not yet three"
    assert flags["label"].iloc[5], "the run completes here, one sample late by design"
    assert flags["label"].sum() == 1


def test_runs_merge_across_a_tolerated_gap():
    mask = np.array([1, 1, 0, 1, 1, 0, 0, 0, 1], dtype=bool)
    assert detect._runs(mask, gap_tolerance=0) == [(0, 1), (3, 4), (8, 8)]
    assert detect._runs(mask, gap_tolerance=1) == [(0, 4), (8, 8)]


def test_minimum_volume_gate_blocks_a_low_traffic_ratio_alert():
    """Three errors in five packets is a 60% error rate and almost never a page."""
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-02-01", periods=6, freq="5min"),
        "device_id": "d", "port_id": "p", "port_role": "wan-primary",
        "score": [9.0] * 6,
        "label": [True] * 6,
        "packets_pps": [0.1, 0.1, 0.1, 500.0, 500.0, 500.0],
    })
    loud = detect.build_alerts(frame, "label", "score", cadence_s=300,
                               policy=detect.AlertPolicy(min_volume_col=None))
    gated = detect.build_alerts(frame, "label", "score", cadence_s=300,
                                policy=detect.AlertPolicy(min_volume_col="packets_pps",
                                                          min_volume=1.0))
    assert len(loud) == 1 and loud["n_samples"].iloc[0] == 6
    assert len(gated) == 1 and gated["n_samples"].iloc[0] == 3


def test_planned_change_marks_an_alert_as_suppressed():
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-02-08 01:00", periods=4, freq="5min"),
        "device_id": "dist-sw-02", "port_id": "port-id7431", "port_role": "backup-storage",
        "score": [9.0] * 4, "label": [True] * 4,
    })
    alerts = detect.build_alerts(frame, "label", "score", cadence_s=300,
                                 changes=wk.load_change_calendar())
    assert len(alerts) == 1
    assert alerts["suppressed_by"].iloc[0] == "CH-01"
    assert not bool(alerts["notified"].iloc[0])


def test_cusum_accumulates_a_drift_a_zscore_would_miss():
    rng = np.random.default_rng(3)
    values = pd.Series(np.concatenate([rng.normal(0, 1, 300), rng.normal(0.8, 1, 300)]))
    z = detect.score_robust_z(values, 60)
    cusum = detect.score_cusum(values, 60)
    assert z.iloc[300:].abs().max() < 5
    assert cusum["cusum_score"].iloc[300:].max() > 1.0
    assert cusum["cusum_signal"].iloc[300:].any()


def test_cusum_resets_after_signalling(telemetry):
    """Without the reset the statistic ratchets and reads as a permanent alarm.

    Measured on the course data before the fix: the score sat above its own
    decision limit for 66.6% of all samples, which no operator would trust.
    """
    frame, contract = telemetry
    port = wk.single_port(frame, "port-id7430")
    window = int(3600 / contract.cadence_s)

    ratcheting = detect.score_cusum(port["traffic_bps"], window, reset_on_signal=False)
    resetting = detect.score_cusum(port["traffic_bps"], window, reset_on_signal=True)

    assert (ratcheting["cusum_score"] > 1.0).mean() > 0.5
    assert (resetting["cusum_score"] > 1.0).mean() < 0.10
    # The crossing itself must still be reported, not swallowed by the reset.
    assert resetting["cusum_score"].max() > 1.0
    assert resetting.loc[resetting["cusum_signal"], "cusum_score"].min() > 1.0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def test_event_recall_counts_events_not_samples():
    events = pd.DataFrame([{
        "event_id": "X", "event_type": "test", "device_id": "d", "port_id": "p",
        "port_role": "wan-primary",
        "start": pd.Timestamp("2026-02-01 10:00"), "end": pd.Timestamp("2026-02-01 11:00"),
    }])
    alerts = pd.DataFrame([{
        "method": "m", "device_id": "d", "port_id": "p", "port_role": "wan-primary",
        "fire_time": pd.Timestamp("2026-02-01 10:05"),
        "clear_time": pd.Timestamp("2026-02-01 10:10"),
        "duration_s": 300.0, "n_samples": 2, "peak_score": 7.0,
        "peak_time": pd.Timestamp("2026-02-01 10:05"), "severity": "warning",
        "severity_score": 1.0, "suppressed_by": "", "notified": True,
    }])
    span = (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-02-02"))
    summary, table, _ = evaluate.evaluate(alerts, events, span)

    assert summary["event_recall"] == 1.0
    assert table["detection_delay_s"].iloc[0] == 300.0
    assert summary["alerts_per_day"] == pytest.approx(1.0, rel=0.01)


def test_accuracy_is_reported_but_useless():
    """A detector that never fires still scores above 0.99 on this class balance."""
    truth = pd.Series([False] * 995 + [True] * 5)
    silent = pd.Series([False] * 1000)
    metrics = evaluate.point_metrics(silent, truth)
    assert metrics["point_accuracy"] > 0.99
    assert metrics["point_recall"] == 0.0


def test_suppressed_alerts_are_counted_not_hidden():
    alerts = pd.DataFrame([
        {"method": "m", "device_id": "d", "port_id": "p", "port_role": "r",
         "fire_time": pd.Timestamp("2026-02-01 01:00"), "clear_time": pd.Timestamp("2026-02-01 01:30"),
         "duration_s": 1800.0, "n_samples": 6, "peak_score": 8.0,
         "peak_time": pd.Timestamp("2026-02-01 01:00"), "severity": "warning",
         "severity_score": 1.0, "suppressed_by": "CH-01", "notified": False},
    ])
    events = pd.DataFrame(columns=["event_id", "event_type", "device_id", "port_id",
                                   "port_role", "start", "end"])
    span = (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-02-02"))
    summary, _, _ = evaluate.evaluate(alerts, events, span)
    assert summary["alerts_suppressed_by_policy"] == 1
    assert summary["alerts_total"] == 0, "suppressed alerts never reach a human"


# ---------------------------------------------------------------------------
# One spec, two renderers
# ---------------------------------------------------------------------------

def test_panel_spec_declares_every_column_it_reads():
    spec = viz.PanelSpec(
        title="t",
        series=[viz.Series("a"), viz.Series("b")],
        band=viz.Band("lo", "hi"),
        markers="flag", shade="truth",
    )
    assert spec.columns() == ["a", "b", "lo", "hi", "flag", "truth"]


def test_grafana_panel_queries_exactly_the_declared_columns():
    spec = viz.PanelSpec(title="t", series=[viz.Series("a")], band=viz.Band("lo", "hi"))
    panel = viz.to_grafana(spec, "prometheus", selector={"port_id": "p1"})
    expressions = " ".join(t["expr"] for t in panel["targets"])
    for column in spec.columns():
        assert f'column="{column}"' in expressions
    assert 'port_id="p1"' in expressions


def test_template_variable_selector_uses_regex_match():
    """Grafana renders an All variable as an alternation, which "=" never matches.

    Left as equality, a dashboard opened on its default value shows nothing and
    looks exactly like a broken exporter.
    """
    spec = viz.PanelSpec(title="t", series=[viz.Series("a")])
    panel = viz.to_grafana(spec, "prometheus", selector={"port_id": "$port"})
    assert 'port_id=~"$port"' in panel["targets"][0]["expr"]


def test_dashboard_serialises():
    import json
    spec = viz.PanelSpec(title="t", series=[viz.Series("a")])
    dash = viz.dashboard("T", "uid", viz.layout([spec], "prometheus"),
                         variables=[viz.port_variable("prometheus")])
    json.loads(json.dumps(dash))
    assert dash["templating"]["list"][0]["name"] == "port"


def test_stat_panel_aggregates_broadcast_scalars():
    """Otherwise the tile shows one identical number per port."""
    panel = viz.stat_panel("Event recall", "eval_event_recall", "prometheus")
    assert panel["targets"][0]["expr"].startswith("max(")


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def test_publish_writes_a_manifest_naming_every_column(tmp_path, monkeypatch):
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-02-01", periods=4, freq="5min"),
        "device_id": "d", "port_id": "p", "value": [1.0, 2.0, 3.0, 4.0],
        "flag": [True, False, True, False],
    })
    monkeypatch.setattr(data.paths, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(wk.grafana.paths, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(wk.grafana.paths, "DROPZONE_DIR", tmp_path / "drop")
    monkeypatch.setattr(wk.grafana.paths, "DROPZONE_CSV", tmp_path / "drop" / "current_results.csv")
    monkeypatch.setattr(wk.grafana.paths, "DROPZONE_MANIFEST",
                        tmp_path / "drop" / "current_results.manifest.json")

    manifest = wk.publish(frame, ["value", "flag"], "unit-test",
                          labels=["device_id", "port_id"],
                          scalars={"eval_thing": 0.5}, quiet=True)

    assert manifest["value_columns"] == ["value", "flag", "eval_thing"]
    written = pd.read_csv(tmp_path / "drop" / "current_results.csv")
    assert set(written["flag"]) == {0.0, 1.0}, "booleans must become numeric gauges"
    assert (written["eval_thing"] == 0.5).all(), "scalars broadcast down every row"
