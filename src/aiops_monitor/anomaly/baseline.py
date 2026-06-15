"""
Statistical baseline anomaly detection (Notebook 2).

Each metric column is flagged using three complementary tests:

- **Z-score**      : (x - rolling_mean_1h) / rolling_std_1h > z_thresh
- **Robust-Z**     : 0.6745 * (x - rolling_median_1h) / rolling_MAD_1d > robust_z_thresh
- **P95 exceedance**: x > rolling_p95_1d (only when x > 0)

A row is flagged on *any* test passing for *any* metric.  The function
operates on the feature DataFrame produced by Notebook 1 (must contain
rolling_mean_1h, rolling_std_1h, rolling_median_1h, rolling_mad_1d,
rolling_p95_1d columns for each metric).

Usage
-----
>>> from aiops_monitor.anomaly.baseline import detect
>>> result = detect(features)
>>> result[result["any_baseline_anomaly"]][["timestamp", "port_id", "baseline_alert_count"]]
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Metrics checked for anomalies (match Notebook 2 flag_map)
_METRIC_MAP: dict[str, str] = {
    "traffic_high":   "traffic_total",
    "packets_high":   "ucast_total",
    "errors_high":    "errors_total",
    "discards_high":  "discards_total",
    "broadcast_high": "broadcast_total",
    "multicast_high": "multicast_total",
    "unknown_high":   "unknown_total",
}


def detect(
    features: pd.DataFrame,
    z_thresh: float = 3.0,
    robust_z_thresh: float = 4.0,
) -> pd.DataFrame:
    """Flag anomalies using statistical baseline tests.

    Parameters
    ----------
    features:
        Feature DataFrame from Notebook 1.  Must contain rolling window
        columns in the form ``{col}_rolling_mean_1h``, ``{col}_rolling_std_1h``,
        ``{col}_rolling_median_1h``, ``{col}_rolling_mad_1d``,
        ``{col}_rolling_p95_1d`` for each metric in ``_METRIC_MAP``.
    z_thresh:
        Standard-deviation threshold for the Z-score test (default 3.0).
    robust_z_thresh:
        Modified-Z threshold for the robust-Z test (default 4.0).

    Returns
    -------
    pd.DataFrame
        Input columns plus per-flag columns, ``baseline_alert_count``,
        and ``any_baseline_anomaly``.
    """
    id_cols = ["timestamp", "device_id", "port_id", "port_role", "event_label", "event_id"]
    metric_cols = list(_METRIC_MAP.values())
    result = features[id_cols + metric_cols].copy()

    for flag, col in _METRIC_MAP.items():
        if col not in features.columns:
            continue

        mean   = features.get(f"{col}_rolling_mean_1h",   pd.Series(dtype=float))
        std    = features.get(f"{col}_rolling_std_1h",    pd.Series(dtype=float)).replace(0, np.nan)
        median = features.get(f"{col}_rolling_median_1h", pd.Series(dtype=float))
        mad    = features.get(f"{col}_rolling_mad_1d",    pd.Series(dtype=float)).replace(0, np.nan)
        p95    = features.get(f"{col}_rolling_p95_1d",    pd.Series(dtype=float))

        z        = ((features[col] - mean) / std).replace([np.inf, -np.inf], 0).fillna(0)
        robust_z = (0.6745 * (features[col] - median) / mad).replace([np.inf, -np.inf], 0).fillna(0)
        pct_exc  = features[col] > p95

        result[f"{col}_z_score"]          = z
        result[f"{col}_robust_z"]         = robust_z
        result[f"{col}_percentile_exceed"] = pct_exc
        result[flag] = (
            (z > z_thresh)
            | (robust_z > robust_z_thresh)
            | (pct_exc & (features[col] > 0))
        )

    flag_cols = [f for f in _METRIC_MAP if f in result.columns]
    result["baseline_alert_count"] = result[flag_cols].sum(axis=1)
    result["any_baseline_anomaly"] = result["baseline_alert_count"] > 0
    return result
