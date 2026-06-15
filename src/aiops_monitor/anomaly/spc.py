"""
Statistical Process Control (SPC) anomaly detection (Notebook 3).

Three control-chart methods are applied per port:

- **Shewhart X-chart**  on ``traffic_total``   → 3-sigma upper control limit
- **EWMA chart**        on ``discard_rate``     → exponentially weighted moving average
- **CUSUM**             on ``error_rate``       → cumulative-sum chart (one-sided, upper)

The baseline statistics (mean, sigma) are estimated from the first 7 days of
*normal* rows for each port.

Usage
-----
>>> from aiops_monitor.anomaly.spc import detect
>>> result = detect(features)
>>> result[result["any_spc_violation"]][["timestamp", "port_id", "shewhart_traffic_violation"]]
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect(
    features: pd.DataFrame,
    ewma_lambda: float = 0.25,
    cusum_k_factor: float = 0.5,
    cusum_h_factor: float = 5.0,
    baseline_days: int = 7,
) -> pd.DataFrame:
    """Apply SPC control charts to network metrics.

    Parameters
    ----------
    features:
        Feature DataFrame from Notebook 1.  Required columns:
        ``timestamp``, ``port_id``, ``event_label``,
        ``traffic_total``, ``discard_rate``, ``error_rate``.
    ewma_lambda:
        Smoothing factor λ for the EWMA chart (0 < λ ≤ 1, default 0.25).
    cusum_k_factor:
        Allowance factor *k* = ``cusum_k_factor × sigma`` (default 0.5).
    cusum_h_factor:
        Decision interval *h* = ``cusum_h_factor × sigma`` (default 5.0).
    baseline_days:
        Number of leading *normal* days used to estimate baseline
        statistics per port (default 7).

    Returns
    -------
    pd.DataFrame
        Per-row SPC results with columns
        ``shewhart_traffic_violation``, ``ewma_discard_violation``,
        ``cusum_error_violation``, and ``any_spc_violation``.
    """
    rows: list[pd.DataFrame] = []
    baseline_rows = baseline_days * 24 * 12  # at 5-min polling

    for _, g in features.groupby("port_id", sort=False):
        g = g.sort_values("timestamp").copy()
        base = g[g["event_label"] == "normal"].head(baseline_rows)

        # ── Shewhart X-chart on traffic_total ────────────────────────────────
        t_mu  = base["traffic_total"].mean()
        t_sig = base["traffic_total"].std()
        g["traffic_center"] = t_mu
        g["traffic_ucl"]    = t_mu + 3 * t_sig
        g["traffic_lcl"]    = max(0.0, t_mu - 3 * t_sig)
        g["shewhart_traffic_violation"] = g["traffic_total"] > g["traffic_ucl"]

        # ── EWMA on discard_rate ──────────────────────────────────────────────
        d_mu  = base["discard_rate"].mean()
        d_sig = base["discard_rate"].std()
        g["ewma_discard_rate"] = g["discard_rate"].ewm(alpha=ewma_lambda, adjust=False).mean()
        g["ewma_discard_ucl"]  = d_mu + 3 * d_sig * np.sqrt(ewma_lambda / (2 - ewma_lambda))
        g["ewma_discard_violation"] = g["ewma_discard_rate"] > g["ewma_discard_ucl"]

        # ── CUSUM on error_rate (one-sided upper) ─────────────────────────────
        e_mu  = base["error_rate"].mean()
        e_sig = max(base["error_rate"].std(), 1e-12)
        k = cusum_k_factor * e_sig
        h = cusum_h_factor * e_sig
        s, pos = 0.0, []
        for v in g["error_rate"].fillna(0):
            s = max(0.0, s + v - e_mu - k)
            pos.append(s)
        g["cusum_error_pos"]       = pos
        g["cusum_error_h"]         = h
        g["cusum_error_violation"] = g["cusum_error_pos"] > h

        rows.append(g)

    result = pd.concat(rows, ignore_index=True)
    result["any_spc_violation"] = result[[
        "shewhart_traffic_violation",
        "ewma_discard_violation",
        "cusum_error_violation",
    ]].any(axis=1)
    return result
