"""Calibration, event scoring, and the honesty probes Lab 08 runs on its own scorecard.

Lab 03 and Lab 04 established the convention this module keeps: compare detectors by fixing a
false-signal budget rather than a threshold, because a Mahalanobis distance and an
IsolationForest score do not live on the same axis and only equal alert volume puts them on one.

What is new here is the second half. A scorecard is an estimate, and Labs 03 to 05 read theirs
as if it were a measurement. Ten incidents cannot separate a detector that catches eight from
one that catches seven, and nothing in the course so far says so out loud. The bootstrap, the
block permutation test and the optimism check are the three ways this file says it.

No statsmodels. The autocorrelation and the Ljung-Box statistic are short enough to write
against numpy and scipy, and the course environment pins neither statsmodels nor shap.
"""
import numpy as np
import pandas as pd
from scipy import stats

SEED = 0


# --------------------------------------------------------------------------- the ladder
class Ladder:
    """A running record of every trial the notebook runs, and what each one measured.

    A lab that prints one table per method teaches that the methods exist. A lab that keeps the
    score across every attempt teaches how the choice was reached, which is the part a beginner
    cannot reconstruct afterwards from a pile of separate outputs.

    Each row carries the measurement and the failure that sent the work to the next row. The
    `next_step` column is the important one, and it is required rather than optional: a trial
    whose result does not change what happens next did not need running.
    """

    def __init__(self):
        self.rows = []

    def record(self, step, trial, metric, value, verdict, next_step):
        self.rows.append({"step": step, "trial": trial, "metric": metric,
                          "value": value, "verdict": verdict, "next_step": next_step})
        return self.rows[-1]

    def table(self, since=None):
        out = pd.DataFrame(self.rows)
        return out if since is None else out[out["step"] >= since].reset_index(drop=True)

    def show(self, since=None):
        table = self.table(since)
        return table[["step", "trial", "metric", "value", "verdict"]]

    def plot(self, metric, ax=None, colour="#7A5AC7", title=None):
        """Trials that share a metric, in the order they were run."""
        import matplotlib.pyplot as plt
        table = self.table()
        table = table[table["metric"] == metric]
        if table.empty:
            raise ValueError(f"no trial recorded the metric {metric!r}")
        ax = ax or plt.gca()
        y = np.arange(len(table))
        ax.barh(y, table["value"].astype(float), color=colour)
        for n, row in enumerate(table.itertuples()):
            ax.text(float(row.value) + 0.01, n, f"{float(row.value):.3f}",
                    va="center", fontsize=11)
        ax.set_yticks(y, [f"{r.step}. {r.trial}" for r in table.itertuples()])
        ax.invert_yaxis()
        ax.set(xlabel=metric, title=title or f"{metric} across every trial, in order")
        return ax


# --------------------------------------------------------------------------- data quality
def data_quality_report(frame, raw_columns, features):
    """Two tables and a header: what the file is, before anything is fitted to it.

    The counter table answers whether a column can be read as cumulative. The feature table
    answers whether a column has enough spread for a deviation score to mean anything.
    """
    counter_rows = []
    for column in raw_columns:
        steps = frame.groupby("port_id")[column].diff().dropna().to_numpy(float)
        counter_rows.append({
            "counter": column,
            "negative_step_frac": round(float((steps < 0).mean()), 3),
            "zero_frac": round(float((frame[column] == 0).mean()), 3),
        })
    feature_rows = []
    for column in features:
        values = frame[column].to_numpy(float)
        centre = np.median(values)
        feature_rows.append({
            "feature": column,
            "zero_frac": round(float((values == 0).mean()), 3),
            "mad": float(np.median(np.abs(values - centre))),
            "cv": round(float(values.std() / (abs(values.mean()) + 1e-12)), 3),
        })
    header = {
        "rows": len(frame),
        "ports": int(frame["port_id"].nunique()),
        "missing_cells": int(frame[list(raw_columns)].isna().sum().sum()),
        "duplicate_port_time": int(frame.duplicated(["port_id", "timestamp"]).sum()),
    }
    return header, pd.DataFrame(counter_rows), pd.DataFrame(feature_rows)


def degenerate_features(frame, features, mask=None, zero_frac_max=0.5):
    """Features a robust z-score cannot scale, and the reason each one qualifies.

    Two ways to fail. A median absolute deviation of exactly zero leaves nothing to divide by.
    A column that is zero most of the time has a defensible MAD and still no usable band. The
    fix is never the same for both, so the reason travels with the name.
    """
    sub = frame if mask is None else frame.loc[np.asarray(mask, bool)]
    out = []
    for column in features:
        values = sub[column].to_numpy(float)
        mad = float(np.median(np.abs(values - np.median(values))))
        zero = float((values == 0).mean())
        reasons = []
        if mad == 0:
            reasons.append("MAD is zero")
        if zero > zero_frac_max:
            reasons.append(f"zero on {zero:.0%} of rows")
        if reasons:
            out.append({"feature": column, "reason": "; ".join(reasons),
                        "mad": mad, "zero_frac": round(zero, 3)})
    return pd.DataFrame(out)


def distribution_table(frame, features, mask=None):
    """Shape of each feature's normal distribution. Normality is assumed by more than it holds."""
    sub = frame if mask is None else frame.loc[np.asarray(mask, bool)]
    rows = []
    for column in features:
        values = sub[column].to_numpy(float)
        rows.append({
            "feature": column,
            "skew": round(float(stats.skew(values)), 2),
            "excess_kurtosis": round(float(stats.kurtosis(values)), 2),
            "normaltest_p": float(stats.normaltest(values).pvalue),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- temporal structure
def acf_values(series, nlags=300):
    """Autocorrelation at lags 0..nlags, normalised so that lag 0 is 1."""
    x = np.asarray(series, float)
    x = x - x.mean()
    denominator = float(x @ x)
    if denominator == 0:
        raise ValueError("cannot compute autocorrelation of a constant series")
    return np.array([1.0] + [float(x[:-k] @ x[k:]) / denominator
                             for k in range(1, nlags + 1)])


def ljung_box(series, lags):
    """Ljung-Box Q and its p-value at each requested lag.

    The null is that the series has no autocorrelation up to that lag. Rejecting it is what
    makes an independence assumption unusable, which is the assumption behind counting alerts as
    if each sample were its own trial.
    """
    x = np.asarray(series, float)
    n = len(x)
    r = acf_values(x, nlags=int(max(lags)))
    rows = []
    for h in lags:
        q = n * (n + 2) * sum(r[k] ** 2 / (n - k) for k in range(1, h + 1))
        rows.append({"lag": int(h), "ljung_box_q": round(float(q), 1),
                     "p_value": float(stats.chi2.sf(q, h))})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- calibration
def signal_onsets(flags):
    """A run of consecutive flags counts once, at its first sample.

    Counting samples instead would rate a four-hour incident as 48 alerts and a detector that
    stays latched as noisier than one that flickers.
    """
    flags = np.asarray(flags, bool)
    return flags & ~np.r_[False, flags[:-1]]


def onsets_per_day(flags, days):
    if days <= 0:
        raise ValueError("days must be positive")
    return float(signal_onsets(flags).sum()) / days


def calibrate_threshold(scores, target_onsets):
    """Lowest threshold whose onset count on this reference is closest to the target.

    Same contract as Lab 03 and Lab 04. Ties break toward the stricter side, so a detector never
    gets credit for a budget it only met by rounding downward.
    """
    scores = np.asarray(scores, float)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("calibration needs one finite score per timestamp")
    candidates = np.r_[-np.inf, np.unique(scores), np.inf]
    ranked = [(abs(int(signal_onsets(scores > t).sum()) - target_onsets),
               int(signal_onsets(scores > t).sum()) > target_onsets, -t, t)
              for t in candidates]
    return float(min(ranked)[-1])


def calibrate_fleet(frame, scores, reference_mask, target_onsets_per_day, cadence_s=300.0):
    """One threshold per (detector, port), each meeting the same false-onset budget.

    Per port rather than fleet-wide, because the five ports carry different roles and a single
    threshold would spend the whole budget on the busiest one.
    """
    reference_mask = np.asarray(reference_mask, bool)
    thresholds = {}
    for port, group in frame.groupby("port_id", sort=True):
        rows = group.index.to_numpy()
        keep = reference_mask[rows]
        if keep.sum() < 2:
            raise ValueError(f"port {port} has {keep.sum()} reference rows")
        days = keep.sum() * cadence_s / 86400
        target = int(round(target_onsets_per_day * days))
        for detector in scores.columns:
            values = scores.loc[rows[keep], detector].to_numpy(float)
            thresholds[(detector, port)] = calibrate_threshold(values, target)
    return thresholds


def flag_fleet(frame, scores, thresholds):
    """Boolean breach per row, using each port's own threshold for that detector."""
    flags = pd.DataFrame(False, index=frame.index, columns=scores.columns)
    for port, group in frame.groupby("port_id", sort=True):
        rows = group.index
        for detector in scores.columns:
            flags.loc[rows, detector] = (
                scores.loc[rows, detector] > thresholds[(detector, port)]).to_numpy()
    return flags


# --------------------------------------------------------------------------- event scoring
def event_windows(frame):
    """One row per (incident, port) window actually present in the telemetry.

    Built from the labels in the file rather than from the catalog, because the catalog files a
    fleet-wide incident against the scope name MULTI and the telemetry is where it is recorded
    which ports it reached.
    """
    hit = frame[frame["event_label"].ne("normal")]
    return (hit.groupby(["event_id", "event_label", "port_id"], as_index=False)
               .agg(start=("timestamp", "min"), end=("timestamp", "max"),
                    n=("timestamp", "size"))
               .rename(columns={"event_label": "event_type"})
               .sort_values(["start", "port_id"]).reset_index(drop=True))


def window_outcomes(frame, flags, windows):
    """Per window: was it caught, and how long did it take. One row per window."""
    flags = np.asarray(flags, bool)
    timestamp = frame["timestamp"].to_numpy()
    port = frame["port_id"].to_numpy()
    rows = []
    for window in windows.itertuples():
        inside = ((port == window.port_id)
                  & (timestamp >= np.datetime64(window.start))
                  & (timestamp <= np.datetime64(window.end)))
        caught = bool((flags & inside).any())
        delay = np.nan
        if caught:
            first = timestamp[flags & inside].min()
            delay = (first - np.datetime64(window.start)) / np.timedelta64(1, "m")
        rows.append({"event_id": window.event_id, "event_type": window.event_type,
                     "port_id": window.port_id, "detected": caught,
                     "delay_min": float(delay)})
    return pd.DataFrame(rows)


def restrict_windows(frame, windows, evaluate_mask):
    """Only the windows whose samples are actually inside the evaluated period.

    A window the evaluation never looks at cannot be caught, so counting it as a miss makes
    every detector look worse in proportion to how much of the month was held back. Recall on a
    held-out slice has to be recall over that slice's own incidents.
    """
    keep = np.asarray(evaluate_mask, bool)
    timestamp = frame["timestamp"].to_numpy()
    port = frame["port_id"].to_numpy()
    rows = []
    for window in windows.itertuples():
        inside = ((port == window.port_id)
                  & (timestamp >= np.datetime64(window.start))
                  & (timestamp <= np.datetime64(window.end)))
        if (inside & keep).any():
            rows.append(window.Index)
    return windows.loc[rows].reset_index(drop=True)


def event_scorecard(frame, flags, windows, evaluate_mask=None, cadence_s=300.0):
    """One row per detector: recall over windows, median delay, and false onsets per port-day.

    False onsets are counted outside every window on that port, so an alert that latches through
    an incident is never charged as noise. The rate is per port per day, which is the unit an
    alert budget is written in and the unit calibrate_fleet() targets. A fleet-wide total would
    read five times larger here and appear to blow a budget it is in fact meeting.
    """
    keep = np.ones(len(frame), bool) if evaluate_mask is None else np.asarray(evaluate_mask, bool)
    windows = restrict_windows(frame, windows, keep)

    inside = np.zeros(len(frame), bool)
    timestamp = frame["timestamp"].to_numpy()
    port = frame["port_id"].to_numpy()
    for window in windows.itertuples():
        inside |= ((port == window.port_id)
                   & (timestamp >= np.datetime64(window.start))
                   & (timestamp <= np.datetime64(window.end)))
    port_days = keep.sum() * cadence_s / 86400          # summed over every port evaluated

    rows = []
    for detector in flags.columns:
        f = flags[detector].to_numpy(bool) & keep
        outcomes = window_outcomes(frame, f, windows)
        false_onsets = 0
        for _, group in frame.assign(_f=f & ~inside).groupby("port_id", sort=True):
            false_onsets += int(signal_onsets(group["_f"].to_numpy(bool)).sum())
        rows.append({
            "detector": detector,
            "windows_caught": int(outcomes["detected"].sum()),
            "windows": len(outcomes),
            "event_recall": round(float(outcomes["detected"].mean()), 3),
            "median_delay_min": (round(float(outcomes.loc[outcomes["detected"],
                                                          "delay_min"].median()), 1)
                                 if outcomes["detected"].any() else np.nan),
            "false_onsets_per_port_day": round(false_onsets / max(port_days, 1e-9), 2),
        })
    return pd.DataFrame(rows).sort_values(
        ["event_recall", "false_onsets_per_port_day"],
        ascending=[False, True]).reset_index(drop=True)


# --------------------------------------------------------------------------- uncertainty
def bootstrap_windows(outcomes, n_boot=2000, seed=SEED):
    """Confidence interval for event recall, resampling whole windows.

    The unit of evidence is an incident, not a sample. Eighteen windows is the entire evidence
    base, so the interval this returns is wide, and that width is the finding. A leaderboard
    ordered on differences narrower than this interval is ordering noise.
    """
    detected = np.asarray(outcomes["detected"], bool)
    n = len(detected)
    if n == 0:
        raise ValueError("no windows to resample")
    rng = np.random.default_rng(seed)
    draws = detected[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"recall": round(float(detected.mean()), 3),
            "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "windows": n}


def block_bootstrap_rate(flags, block, n_boot=1000, seed=SEED, cadence_s=300.0):
    """Confidence interval for the false-onset rate, resampling contiguous blocks.

    Blocks rather than samples, because alert flags are autocorrelated: one breach makes the next
    sample far more likely to breach than its marginal rate suggests. A sample bootstrap would
    shatter those runs and report an interval several times too narrow.
    """
    flags = np.asarray(flags, bool)
    n = len(flags)
    if block <= 0 or block > n:
        raise ValueError(f"block must lie in [1, {n}], got {block}")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    rates = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        sample = np.concatenate([flags[s:s + block] for s in starts])[:n]
        rates.append(signal_onsets(sample).sum() / (n * cadence_s / 86400))
    lo, hi = np.percentile(rates, [2.5, 97.5])
    return {"onsets_per_day": round(float(signal_onsets(flags).sum() / (n * cadence_s / 86400)), 2),
            "ci95": [round(float(lo), 2), round(float(hi), 2)]}


def block_permutation_test(score, labels, block, n_perm=1000, seed=SEED):
    """Is this score better than chance at separating incident samples, given the autocorrelation?

    The null shifts the score circularly in whole blocks rather than shuffling samples. Shuffling
    destroys the runs that make a smooth score look informative, so a pointwise permutation test
    reports a p-value that is far too small on any series with memory. That is the same mistake
    the block bootstrap above exists to avoid, and a file that block-bootstraps and then
    pointwise-permutes is contradicting itself.
    """
    score = np.asarray(score, float)
    labels = np.asarray(labels, bool)
    n = len(score)
    if labels.sum() == 0 or labels.all():
        raise ValueError("permutation test needs both classes present")
    observed = float(score[labels].mean() - score[~labels].mean())
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    null = []
    for _ in range(n_perm):
        order = rng.permutation(n_blocks)
        shuffled = np.concatenate(
            [score[i * block:(i + 1) * block] for i in order])[:n]
        null.append(shuffled[labels].mean() - shuffled[~labels].mean())
    null = np.asarray(null)
    return {"observed_gap": round(observed, 3),
            "null_mean_gap": round(float(null.mean()), 3),
            "p_value": round(float((1 + (null >= observed).sum()) / (n_perm + 1)), 4)}


# --------------------------------------------------------------------------- honesty probes
def best_threshold_on_labels(frame, score, windows, evaluate_mask, port,
                             false_onset_cap, n_candidates=200):
    """The threshold a tuner would pick for one port if it were allowed to see the answers.

    Catch the most windows that the false-onset cap permits, and break ties toward the quieter
    threshold. This is the optimistic bound rather than a method: nobody has these labels on the
    day the threshold has to be set.
    """
    keep = np.asarray(evaluate_mask, bool)
    rows = (frame["port_id"] == port).to_numpy() & keep
    if not rows.any():
        raise ValueError(f"port {port} has no rows in the evaluated period")
    s = np.asarray(score, float)[rows]
    sub = frame.loc[rows]
    port_windows = windows[windows["port_id"] == port]

    timestamp = sub["timestamp"].to_numpy()
    inside = np.zeros(rows.sum(), bool)
    spans = []
    for window in port_windows.itertuples():
        span = ((timestamp >= np.datetime64(window.start))
                & (timestamp <= np.datetime64(window.end)))
        spans.append(span)
        inside |= span

    best = (-1, 0, -np.inf)
    for candidate in np.quantile(s, np.linspace(0.5, 1.0, n_candidates)):
        breach = s > candidate
        false_onsets = int(signal_onsets(breach & ~inside).sum())
        if false_onsets > false_onset_cap:
            continue
        caught = sum(1 for span in spans if (breach & span).any())
        key = (caught, -false_onsets, candidate)
        if key > best:
            best = key
    if best[0] < 0:
        return float(s.max())          # nothing meets the cap; fire on nothing
    return float(best[2])


def threshold_optimism(frame, scores, windows, tune_mask, test_mask,
                       target_onsets_per_day, cadence_s=300.0):
    """The same detector scored twice: threshold set before the answers, and after them.

    The held-out arm calibrates on a quiet stretch that carries no incidents, which is all an
    operator has on the day. The tuned arm is handed the test labels and picks the threshold that
    catches the most windows within the same false-onset allowance. The gap between the two is
    what a scorecard overstates when the threshold was chosen by looking at the answer, and it is
    the reason a tuned number reported without its held-out twin is not evidence of anything.
    """
    test_mask = np.asarray(test_mask, bool)
    evaluated = restrict_windows(frame, windows, test_mask)
    ports = sorted(frame.loc[test_mask, "port_id"].unique())
    days = test_mask.sum() * cadence_s / 86400 / max(len(ports), 1)
    cap = int(round(target_onsets_per_day * days))

    rows = []
    for detector in scores.columns:
        honest = calibrate_fleet(frame, scores[[detector]], tune_mask,
                                 target_onsets_per_day, cadence_s)
        leaked = {(detector, port): best_threshold_on_labels(
            frame, scores[detector], evaluated, test_mask, port, cap) for port in ports}
        out = {}
        for name, thresholds in (("held_out", honest), ("tuned_on_test", leaked)):
            flags = flag_fleet(frame, scores[[detector]], thresholds)
            card = event_scorecard(frame, flags, evaluated,
                                   evaluate_mask=test_mask, cadence_s=cadence_s)
            out[f"recall_{name}"] = float(card["event_recall"].iloc[0])
            out[f"false_{name}"] = float(card["false_onsets_per_port_day"].iloc[0])
        rows.append({"detector": detector, **out,
                     "recall_optimism": round(out["recall_tuned_on_test"]
                                              - out["recall_held_out"], 3)})
    return pd.DataFrame(rows).sort_values("recall_optimism",
                                          ascending=False).reset_index(drop=True)


def drift_ks(frame, features, early_mask, late_mask):
    """Two-sample test between two stretches of normal traffic, feature by feature.

    A model fitted in February and used in March is only valid while normal stays normal. This
    compares like with like: incident windows and announced changes are excluded from both sides,
    so anything the test finds is drift rather than an event.
    """
    rows = []
    for column in features:
        a = frame.loc[np.asarray(early_mask, bool), column].to_numpy(float)
        b = frame.loc[np.asarray(late_mask, bool), column].to_numpy(float)
        result = stats.ks_2samp(a, b)
        rows.append({"feature": column,
                     "ks_stat": round(float(result.statistic), 3),
                     "p_value": float(result.pvalue),
                     "median_early": float(np.median(a)),
                     "median_late": float(np.median(b))})
    return pd.DataFrame(rows).sort_values("ks_stat", ascending=False).reset_index(drop=True)


def breach_independence(flags):
    """How far alert samples are from independent, measured against their own marginal rate.

    Under independence, adjacent breaches would occur at the square of the breach rate. The ratio
    this returns is how many times more often they actually occur together. Every alert-volume
    calculation that multiplies a per-sample rate by the number of samples is wrong by roughly
    this factor.
    """
    b = np.asarray(flags, bool)
    n = len(b)
    p = float(b.mean())
    observed = int(np.sum(b[:-1] & b[1:]))
    expected = (n - 1) * p * p
    return {"breach_rate": round(p, 5), "observed_adjacent": observed,
            "expected_if_independent": round(expected, 1),
            "ratio": round(observed / expected, 1) if expected > 0 else np.nan}
