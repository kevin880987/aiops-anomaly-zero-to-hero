"""Scoring a detector the way an operations team would.

Per-point accuracy is the wrong headline number for time-series monitoring. An
incident that runs for thirty minutes does not need to be caught at every one of
its samples; it needs to be caught once, early, without burying the responder.
So the metrics that matter here are event-level recall, detection delay, and
alert burden, with point-level precision and recall kept only as a diagnostic.

Everything is computed against explicit ground truth so that two cadets tuning
different thresholds can compare results on the same axis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import scope_matches


def point_metrics(labels: pd.Series, truth: pd.Series) -> dict:
    """Per-sample confusion. Useful for diagnosis, misleading as a headline."""
    labels = labels.fillna(False).to_numpy(dtype=bool)
    truth = truth.fillna(False).to_numpy(dtype=bool)
    tp = int(np.sum(labels & truth))
    fp = int(np.sum(labels & ~truth))
    fn = int(np.sum(~labels & truth))
    tn = int(np.sum(~labels & ~truth))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "point_precision": precision,
        "point_recall": recall,
        "point_f1": f1,
        # Reported to show why it must not be used: with a 0.7% positive rate,
        # a detector that never fires still scores above 0.99.
        "point_accuracy": (tp + tn) / max(tp + tn + fp + fn, 1),
    }


def match_alerts_to_events(
    alerts: pd.DataFrame,
    events: pd.DataFrame,
    tolerance_s: float = 0.0,
    unit_col: str = "port_id",
    notified_only: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Overlap-match alerts against ground-truth event windows.

    An alert matches an event when it is on the same port and their intervals
    intersect, widened by `tolerance_s` so that an alert firing just before the
    labelled start counts as an early detection rather than a false positive.

    Returns (events with detection outcome, alerts with match outcome).
    """
    working = alerts.copy()
    if notified_only and "notified" in working.columns:
        working = working[working["notified"]]
    working = working.reset_index(drop=True)

    pad = pd.Timedelta(seconds=tolerance_s)
    event_rows = []
    matched_alert_idx: set[int] = set()

    for event in events.itertuples():
        hits = working[
            (working[unit_col] == getattr(event, unit_col))
            & (working["fire_time"] <= event.end + pad)
            & (working["clear_time"] >= event.start - pad)
        ]
        detected = len(hits) > 0
        matched_alert_idx.update(hits.index.tolist())
        first_fire = hits["fire_time"].min() if detected else pd.NaT
        event_rows.append({
            "event_id": event.event_id,
            "event_type": event.event_type,
            unit_col: getattr(event, unit_col),
            "port_role": getattr(event, "port_role", ""),
            "start": event.start,
            "end": event.end,
            "detected": detected,
            "n_alerts": int(len(hits)),
            "first_fire": first_fire,
            "detection_delay_s": (first_fire - event.start).total_seconds() if detected else np.nan,
            "peak_score": float(hits["peak_score"].max()) if detected else np.nan,
        })

    working["matched_event"] = working.index.isin(matched_alert_idx)
    columns = ["event_id", "event_type", unit_col, "port_role", "start", "end",
               "detected", "n_alerts", "first_fire", "detection_delay_s", "peak_score"]
    # An empty ground-truth set is a legitimate input: it is what you have on the
    # first day, before anything has been labelled. Returning a frame without
    # columns would make every caller crash on the first column access.
    table = pd.DataFrame(event_rows, columns=None if event_rows else columns)
    if not event_rows:
        table = table.astype({"detected": bool, "n_alerts": int})
    return table, working


def evaluate(
    alerts: pd.DataFrame,
    events: pd.DataFrame,
    span: tuple[pd.Timestamp, pd.Timestamp],
    labels: pd.Series | None = None,
    truth: pd.Series | None = None,
    changes: pd.DataFrame | None = None,
    tolerance_s: float = 0.0,
    method: str = "",
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Full operational scorecard for one detector configuration.

    Returns (summary, per-event table, per-alert table).
    """
    event_table, alert_table = match_alerts_to_events(alerts, events, tolerance_s=tolerance_s)

    # Alerts the policy suppressed never reach a human, so they are excluded from
    # precision and burden. They are still counted, because suppression that is
    # not visible cannot be audited: a rule that silently swallows a real
    # incident looks exactly like a rule that works.
    n_suppressed = int((~alerts["notified"]).sum()) if "notified" in alerts.columns else 0

    n_events = len(event_table)
    n_detected = int(event_table["detected"].sum()) if n_events else 0
    delays = event_table.loc[event_table["detected"], "detection_delay_s"].dropna()

    n_alerts = len(alert_table)
    n_true_alerts = int(alert_table["matched_event"].sum()) if n_alerts else 0
    false_alerts = alert_table[~alert_table["matched_event"]] if n_alerts else alert_table

    # A false alert that lands inside a declared change window and was *not*
    # suppressed is a suppression failure with a known fix. One that lands on
    # ordinary traffic is a modelling failure. Reporting them together hides
    # which of the two problems you actually have.
    n_false_on_change = 0
    if changes is not None and len(changes) and len(false_alerts):
        for alert in false_alerts.itertuples():
            for change in changes.itertuples():
                if not scope_matches(change.scope, getattr(alert, "device_id", ""), getattr(alert, "port_id", "")):
                    continue
                if alert.fire_time <= change.end and alert.clear_time >= change.start:
                    n_false_on_change += 1
                    break

    days = max((span[1] - span[0]).total_seconds() / 86400.0, 1e-9)
    duplicates = event_table.loc[event_table["detected"], "n_alerts"]

    summary = {
        "method": method,
        "events_total": n_events,
        "events_detected": n_detected,
        "event_recall": n_detected / n_events if n_events else 0.0,
        "alerts_total": n_alerts,
        "alerts_suppressed_by_policy": n_suppressed,
        "alerts_matching_event": n_true_alerts,
        "event_precision": n_true_alerts / n_alerts if n_alerts else 0.0,
        "false_alerts": n_alerts - n_true_alerts,
        "false_alerts_on_planned_change": n_false_on_change,
        "false_alerts_unexplained": (n_alerts - n_true_alerts) - n_false_on_change,
        "alerts_per_day": n_alerts / days,
        "median_detection_delay_min": float(delays.median() / 60) if len(delays) else np.nan,
        "max_detection_delay_min": float(delays.max() / 60) if len(delays) else np.nan,
        "duplicate_alerts_per_event": float(duplicates.mean()) if len(duplicates) else 0.0,
        "median_alert_duration_min": float(alert_table["duration_s"].median() / 60) if n_alerts else np.nan,
    }
    if labels is not None and truth is not None:
        summary.update(point_metrics(labels, truth))
    return summary, event_table, alert_table


def sweep(
    frame: pd.DataFrame,
    score_col: str,
    events: pd.DataFrame,
    span: tuple[pd.Timestamp, pd.Timestamp],
    thresholds,
    build_alerts_fn,
    truth: pd.Series | None = None,
    direction: str = "high",
    n_consecutive: int = 3,
) -> pd.DataFrame:
    """Trace the operating curve as the decision threshold moves.

    Lowering a threshold buys event recall and shorter detection delay, and pays
    for it in alerts per day. That exchange rate is the actual design decision;
    the threshold is only how it is written down. Plot the result and pick the
    point your on-call rota can absorb.
    """
    from . import detect

    rows = []
    for threshold in thresholds:
        flags = detect.confirm(frame[score_col], threshold, n_consecutive, direction=direction)
        working = frame.assign(_label=flags["label"])
        alerts = build_alerts_fn(working, "_label", score_col)
        summary, _, _ = evaluate(
            alerts, events, span,
            labels=flags["label"] if truth is not None else None,
            truth=truth,
        )
        summary["threshold"] = threshold
        summary["n_consecutive"] = n_consecutive
        rows.append(summary)
    return pd.DataFrame(rows)


def comparison_table(summaries: list[dict], columns: list[str] | None = None) -> pd.DataFrame:
    """Side-by-side scorecard for several detectors."""
    columns = columns or [
        "method", "event_recall", "events_detected", "events_total",
        "alerts_per_day", "false_alerts_unexplained",
        "median_detection_delay_min", "duplicate_alerts_per_event",
    ]
    table = pd.DataFrame(summaries)
    keep = [c for c in columns if c in table.columns]
    return table[keep].sort_values("event_recall", ascending=False).reset_index(drop=True)
