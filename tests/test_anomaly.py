"""Tests for aiops_monitor.anomaly (baseline, spc, ml)"""
import numpy as np
import pandas as pd
import pytest
from aiops_monitor.simulator.rrd import generate
from aiops_monitor.anomaly.spc import detect as spc_detect
from aiops_monitor.anomaly.ml import detect as ml_detect


@pytest.fixture(scope="module")
def raw_metrics():
    metrics, _ = generate(days=10, seed=42)
    return metrics


def _make_features(metrics: pd.DataFrame) -> pd.DataFrame:
    """Minimal feature engineering matching Notebook 1 column names."""
    rows = []
    for _, g in metrics.groupby("port_id", sort=False):
        g = g.sort_values("timestamp").copy()
        g["traffic_total"]   = g["INOCTETS"] + g["OUTOCTETS"]
        g["ucast_total"]     = g["INUCASTPKTS"] + g["OUTUCASTPKTS"]
        g["errors_total"]    = g["INERRORS"] + g["OUTERRORS"]
        g["discards_total"]  = g["INDISCARDS"] + g["OUTDISCARDS"]
        g["broadcast_total"] = g["INBROADCASTPKTS"] + g["OUTBROADCASTPKTS"]
        g["multicast_total"] = g["INMULTICASTPKTS"] + g["OUTMULTICASTPKTS"]
        g["unknown_total"]   = g["INUNKNOWNPROTOS"]
        g["error_rate"]   = g["errors_total"]   / g["traffic_total"].replace(0, np.nan)
        g["discard_rate"] = g["discards_total"] / g["traffic_total"].replace(0, np.nan)
        g["avg_packet_size"] = g["traffic_total"] / g["ucast_total"].replace(0, np.nan)
        g["broadcast_ratio"] = g["broadcast_total"] / g["ucast_total"].replace(0, np.nan)
        g["multicast_ratio"] = g["multicast_total"] / g["ucast_total"].replace(0, np.nan)
        g = g.fillna(0)
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def features(raw_metrics):
    return _make_features(raw_metrics)


# ── SPC tests ─────────────────────────────────────────────────────────────────

def test_spc_returns_dataframe(features):
    result = spc_detect(features)
    assert isinstance(result, pd.DataFrame)


def test_spc_violation_columns(features):
    result = spc_detect(features)
    for col in ("shewhart_traffic_violation", "ewma_discard_violation",
                "cusum_error_violation", "any_spc_violation"):
        assert col in result.columns


def test_spc_flags_some_anomalies(features):
    result = spc_detect(features)
    assert result["any_spc_violation"].any(), "Expected at least one SPC violation in 10 days of data"


def test_spc_preserves_row_count(features):
    result = spc_detect(features)
    assert len(result) == len(features)


# ── ML tests ──────────────────────────────────────────────────────────────────

def test_ml_returns_dataframe(features):
    result = ml_detect(features)
    assert isinstance(result, pd.DataFrame)


def test_ml_score_columns(features):
    result = ml_detect(features)
    assert "ml_anomaly_score" in result.columns
    assert "ml_is_anomaly" in result.columns
    assert "ml_method" in result.columns


def test_ml_anomaly_rate_reasonable(features):
    result = ml_detect(features, contamination=0.035)
    rate = result["ml_is_anomaly"].mean()
    # IsolationForest with contamination=0.035 should flag roughly 3.5%
    assert 0.02 < rate < 0.06, f"Unexpected anomaly rate: {rate:.3f}"


def test_ml_scores_nonnegative(features):
    result = ml_detect(features)
    assert (result["ml_anomaly_score"] >= 0).all()
