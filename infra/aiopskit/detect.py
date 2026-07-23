"""Three layers: anomaly score, anomaly label, alert.

Unit 03 draws a line between a continuous measure of deviation, the binary
judgement that follows a threshold, and the notification that reaches a human.
Collapsing them is what produces alert storms, because every operational
condition worth applying -- minimum traffic volume, minimum duration, planned
maintenance, severity, deduplication -- lives in the gap between the label and
the alert.

Scoring functions return a signed score on the caller's index. `confirm` turns a
score into a label. `build_alerts` turns labels into notifications.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import baselines
from .data import scope_matches

# Business weight per port role, used by the default severity model. A workshop
# starting point, not a fact: the operator owns this table.
DEFAULT_ROLE_WEIGHT = {
    "wan-primary": 1.0,
    "server-uplink": 0.9,
    "wan-secondary": 0.6,
    "office-vlan": 0.5,
    "backup-storage": 0.3,
}


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

def score_fixed(values: pd.Series, limit: float, tolerance: float | None = None) -> pd.Series:
    """Distance from a hard limit, expressed in units of `tolerance`.

    With the default tolerance the score crosses 1.0 exactly at the limit, which
    puts a fixed threshold on the same axis as every statistical detector.
    """
    tolerance = tolerance if tolerance else abs(limit) * 0.1 or 1.0
    center, scale = baselines.fixed(values, limit - tolerance, tolerance)
    return baselines.deviation_score(values, center, scale)


def score_rolling_z(values: pd.Series, window: int) -> pd.Series:
    center, scale = baselines.rolling_mean(values, window)
    return baselines.deviation_score(values, center, scale)


def score_robust_z(values: pd.Series, window: int) -> pd.Series:
    center, scale = baselines.rolling_robust(values, window)
    return baselines.deviation_score(values, center, scale)


def score_seasonal_z(
    frame: pd.DataFrame,
    value_col: str,
    by: str = "daytype_hour",
    train_mask: pd.Series | None = None,
) -> pd.Series:
    center, scale = baselines.seasonal(frame, value_col, by=by, train_mask=train_mask)
    return baselines.deviation_score(frame[value_col].astype(float), center, scale)


def score_peer_z(frame: pd.DataFrame, value_col: str, unit_col: str = "port_id") -> pd.Series:
    center, scale = baselines.peer(frame, value_col, unit_col=unit_col)
    return baselines.deviation_score(frame[value_col].astype(float), center, scale)


def score_dual_ma(values: pd.Series, short: int, long: int) -> pd.Series:
    """Relative divergence between a fast and a slow moving average.

    Answers "has the level moved" rather than "is this point far out". The cost
    is latency: the slow average must first stop tracking the new level.
    """
    fast = values.rolling(short, min_periods=max(2, short // 2)).mean()
    slow = values.rolling(long, min_periods=max(2, long // 2)).mean()
    return (fast - slow) / (slow.abs() + 1e-9)


def score_cusum(
    values: pd.Series,
    window: int,
    k: float = 0.5,
    h: float = 5.0,
    robust: bool = True,
    reset_on_signal: bool = True,
) -> pd.DataFrame:
    """Cumulative sum of standardised deviation, with slack `k` and limit `h`.

    A rolling z-score forgets each sample the moment the next arrives. CUSUM
    accumulates, so a drift of half a sigma that never once looks alarming still
    crosses `h` after enough samples. That is the trade: less sensitivity to a
    single point, far more to persistence.

    An arm that crosses `h` is reset to zero, which is what makes the chart a
    detector rather than a running total. Without the reset the statistic
    ratchets upward and never comes back: measured on this dataset, the score
    then sits above its own decision limit for two thirds of all samples, which
    would read as a permanent alarm. Turn `reset_on_signal` off only to see that
    failure for yourself.

    Returns both arms, the normalised score where 1.0 is the decision limit, and
    the signal flag.
    """
    center, scale = (baselines.rolling_robust(values, window) if robust
                     else baselines.rolling_mean(values, window))
    z = ((values - center) / scale).fillna(0.0).to_numpy(dtype=float)

    n = len(z)
    pos = np.zeros(n)
    neg = np.zeros(n)
    score = np.zeros(n)
    signal = np.zeros(n, dtype=bool)
    carry_pos = carry_neg = 0.0
    for i in range(1, n):
        pos[i] = max(0.0, carry_pos + z[i] - k)
        neg[i] = max(0.0, carry_neg - z[i] - k)
        # Report the height reached, then reset. Resetting before reporting would
        # hide the very crossing the statistic exists to announce.
        score[i] = max(pos[i], neg[i]) / h
        crossed = pos[i] > h or neg[i] > h
        signal[i] = crossed
        carry_pos, carry_neg = (0.0, 0.0) if (crossed and reset_on_signal) else (pos[i], neg[i])

    return pd.DataFrame({
        "cusum_pos": pos,
        "cusum_neg": neg,
        "cusum_score": score,
        "cusum_signal": signal,
    }, index=values.index)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def confirm(
    score: pd.Series,
    threshold: float,
    n_consecutive: int = 1,
    direction: str = "high",
) -> pd.DataFrame:
    """Threshold a score, then require `n_consecutive` samples before believing it.

    Two columns come back because they answer different questions. `breach` is
    where the score crossed; `label` is where the detector is prepared to say so.
    The gap between the first breach and the first label is the confirmation
    latency you pay for the noise you suppressed.
    """
    if direction == "high":
        breach = score > threshold
    elif direction == "low":
        breach = score < -threshold
    else:
        breach = score.abs() > threshold

    breach = breach.fillna(False)
    if n_consecutive <= 1:
        label = breach
    else:
        run = breach.astype(int).rolling(n_consecutive, min_periods=n_consecutive).sum()
        label = (run >= n_consecutive).fillna(False)
    return pd.DataFrame({"breach": breach, "label": label}, index=score.index)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@dataclass
class AlertPolicy:
    """Everything between a label and a page.

    min_volume_col / min_volume
        Ratio metrics are unstable when the denominator is small. Three errors
        out of five packets at 04:00 is a 60% error rate and almost never worth
        waking anyone. Gate on absolute volume before trusting a ratio.
    gap_tolerance
        Samples a run may drop below threshold without splitting into a second
        alert. Prevents one event from paging twice.
    cooldown_s
        Minimum quiet period before the same series may alert again.
    suppress_scope
        Planned changes and maintenance windows. Suppressed candidates are kept
        with a reason so that suppression can be audited rather than trusted.
    """

    min_consecutive: int = 3
    gap_tolerance: int = 1
    min_volume_col: str | None = None
    min_volume: float = 0.0
    cooldown_s: float = 0.0
    warning_score: float = 1.0
    critical_score: float = 2.0
    critical_duration_s: float = 1800.0
    role_weight: dict | None = None


def _runs(mask: np.ndarray, gap_tolerance: int) -> list[tuple[int, int]]:
    """Contiguous True runs, merged across gaps of at most `gap_tolerance`."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    splits = np.flatnonzero(np.diff(idx) > gap_tolerance + 1)
    starts = np.concatenate([[idx[0]], idx[splits + 1]])
    ends = np.concatenate([idx[splits], [idx[-1]]])
    return list(zip(starts.tolist(), ends.tolist()))


def _severity(peak_score: float, duration_s: float, weight: float, policy: AlertPolicy) -> tuple[str, float]:
    """Severity as deviation x duration x business impact, not deviation alone.

    The same score on a backup port at 02:00 and on the primary WAN uplink at
    10:00 are not the same operational fact, and a severity model that cannot
    express that will have its output ignored.
    """
    deviation = min(peak_score / max(policy.critical_score, 1e-9), 2.0)
    persistence = min(duration_s / max(policy.critical_duration_s, 1e-9), 2.0)
    score = (0.5 * deviation + 0.3 * persistence + 0.2 * 2 * weight)
    if score >= 1.0:
        return "critical", score
    if score >= 0.55:
        return "warning", score
    return "info", score


def build_alerts(
    frame: pd.DataFrame,
    label_col: str,
    score_col: str,
    policy: AlertPolicy | None = None,
    cadence_s: float = 300.0,
    group_cols: tuple[str, ...] = ("device_id", "port_id"),
    ts_col: str = "timestamp",
    changes: pd.DataFrame | None = None,
    method: str = "",
    evidence_cols: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Collapse per-sample labels into the alert records an operator would receive.

    One row per notification, carrying the evidence a responder needs to act
    without opening a notebook: what fired, on what, against which baseline,
    how far out, for how long, and whether a planned change explains it.
    """
    policy = policy or AlertPolicy()
    role_weight = policy.role_weight or DEFAULT_ROLE_WEIGHT
    records: list[dict] = []

    for keys, group in frame.groupby(list(group_cols), observed=True, sort=False):
        group = group.sort_values(ts_col)
        keys = keys if isinstance(keys, tuple) else (keys,)
        key_map = dict(zip(group_cols, keys))

        gate = np.array(group[label_col].fillna(False), dtype=bool)
        if policy.min_volume_col and policy.min_volume_col in group.columns:
            volume = np.asarray(group[policy.min_volume_col], dtype=float)
            gate = gate & (volume >= policy.min_volume)

        last_end: pd.Timestamp | None = None
        for start_i, end_i in _runs(gate, policy.gap_tolerance):
            window = group.iloc[start_i: end_i + 1]
            fire_time = window[ts_col].iloc[0]
            clear_time = window[ts_col].iloc[-1]
            duration_s = float((clear_time - fire_time).total_seconds()) + cadence_s

            if last_end is not None and policy.cooldown_s > 0:
                if (fire_time - last_end).total_seconds() < policy.cooldown_s:
                    continue
            last_end = clear_time

            scores = window[score_col].astype(float)
            peak_score = float(scores.abs().max())
            peak_time = window[ts_col].iloc[int(np.asarray(scores.abs()).argmax())]

            role = str(window["port_role"].iloc[0]) if "port_role" in window.columns else str(key_map.get("port_role", ""))
            weight = role_weight.get(role, 0.5)
            severity, severity_score = _severity(peak_score, duration_s, weight, policy)

            suppressed_by = ""
            if changes is not None and len(changes):
                for change in changes.itertuples():
                    if not scope_matches(change.scope, key_map.get("device_id", ""), key_map.get("port_id", "")):
                        continue
                    if fire_time <= change.end and clear_time >= change.start:
                        suppressed_by = str(change.change_id)
                        break

            record = {
                "method": method or score_col,
                **key_map,
                "port_role": role,
                "fire_time": fire_time,
                "clear_time": clear_time,
                "duration_s": duration_s,
                "n_samples": int(len(window)),
                "peak_score": peak_score,
                "peak_time": peak_time,
                "severity": severity,
                "severity_score": round(severity_score, 3),
                "suppressed_by": suppressed_by,
                "notified": suppressed_by == "",
            }
            for column in evidence_cols:
                if column in window.columns:
                    record[f"evidence_{column}"] = float(window[column].astype(float).abs().max())
            records.append(record)

    if not records:
        return pd.DataFrame(columns=[
            "method", *group_cols, "port_role", "fire_time", "clear_time", "duration_s",
            "n_samples", "peak_score", "peak_time", "severity", "severity_score",
            "suppressed_by", "notified",
        ])
    return pd.DataFrame(records).sort_values("fire_time").reset_index(drop=True)


def notification_text(alert: pd.Series, metric: str, baseline_desc: str, dashboard_url: str = "", runbook: str = "") -> str:
    """The message body an on-call engineer actually receives.

    Unit 03 lists what a usable notification carries: metric and current value,
    baseline, threshold, score, start time, duration, affected instance,
    dashboard, runbook, rule version. A notification missing these forces the
    responder to reconstruct the context that the detector already had.
    """
    lines = [
        f"[{alert['severity'].upper()}] {metric} on {alert.get('port_id', '?')} ({alert.get('port_role', '?')})",
        f"  detector      {alert['method']}  vs  {baseline_desc}",
        f"  deviation     {alert['peak_score']:.2f} (peak at {alert['peak_time']})",
        f"  started       {alert['fire_time']}",
        f"  duration      {alert['duration_s'] / 60:.0f} min over {alert['n_samples']} samples",
        f"  severity      {alert['severity']} (score {alert['severity_score']})",
    ]
    if alert.get("suppressed_by"):
        lines.append(f"  suppressed    planned change {alert['suppressed_by']}")
    if dashboard_url:
        lines.append(f"  dashboard     {dashboard_url}")
    if runbook:
        lines.append(f"  runbook       {runbook}")
    return "\n".join(lines)
