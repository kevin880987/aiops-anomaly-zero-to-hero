"""
Unsupervised ML anomaly detection — Isolation Forest (Notebook 4).

For each port, 30-minute rolling window statistics (mean, std, max, min,
p95, slope) are computed for a fixed set of metric columns.  An
``IsolationForest`` model is then fit on the combined feature matrix and
used to score every row.

Usage
-----
>>> from aiops_monitor.anomaly.ml import detect
>>> result = detect(features)
>>> result[result["ml_is_anomaly"]][["timestamp", "port_id", "ml_anomaly_score"]]
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

# Columns used to build rolling-window features
_MODEL_FEATURES = [
    "traffic_total",
    "ucast_total",
    "avg_packet_size",
    "error_rate",
    "discard_rate",
    "broadcast_ratio",
    "multicast_ratio",
    "unknown_total",
]


def _build_window_features(features: pd.DataFrame) -> pd.DataFrame:
    """Compute 30-min rolling statistics per port."""
    port_dfs: list[pd.DataFrame] = []

    for _, g in features.groupby("port_id", sort=False):
        g = g.sort_values("timestamp").set_index("timestamp")
        meta = g[["device_id", "port_id", "port_role", "event_label", "event_id"]].copy()
        generated: dict[str, pd.Series] = {}

        for col in _MODEL_FEATURES:
            if col not in g.columns:
                continue
            roll = g[col].rolling("30min", min_periods=3)
            generated[f"{col}_mean_30m"] = roll.mean()
            generated[f"{col}_std_30m"]  = roll.std()
            generated[f"{col}_max_30m"]  = roll.max()
            generated[f"{col}_min_30m"]  = roll.min()
            generated[f"{col}_p95_30m"]  = roll.quantile(0.95)
            generated[f"{col}_slope_30m"] = g[col].diff(6)

        wf = pd.concat([meta, pd.DataFrame(generated, index=meta.index)], axis=1)
        port_dfs.append(wf.reset_index())

    return pd.concat(port_dfs, ignore_index=True)


def detect(
    features: pd.DataFrame,
    contamination: float = 0.035,
    n_estimators: int = 250,
    random_state: int = 42,
) -> pd.DataFrame:
    """Detect anomalies using an Isolation Forest on rolling window features.

    Parameters
    ----------
    features:
        Feature DataFrame from Notebook 1.
    contamination:
        Expected fraction of anomalous rows (default 0.035 ≈ 3.5%).
    n_estimators:
        Number of trees in the Isolation Forest (default 250).
    random_state:
        Random seed for reproducibility (default 42).

    Returns
    -------
    pd.DataFrame
        Input rows plus ``ml_anomaly_score``, ``ml_is_anomaly``,
        and ``ml_method`` columns.
    """
    windows = _build_window_features(features)
    X_cols = [c for c in windows.columns if c.endswith(
        ("mean_30m", "std_30m", "max_30m", "min_30m", "p95_30m", "slope_30m")
    )]
    X = windows[X_cols].replace([np.inf, -np.inf], 0).fillna(0)

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    model.fit(X_scaled)

    windows["ml_anomaly_score"] = -model.score_samples(X_scaled)
    windows["ml_is_anomaly"]    = model.predict(X_scaled) == -1
    windows["ml_method"]        = "IsolationForest"
    return windows
