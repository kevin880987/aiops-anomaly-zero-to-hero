"""Baselines: the comparison reference an observation is judged against.

Unit 03 lists seven sources of a normal baseline. Five of them are computable
from telemetry alone and are implemented here: a fixed engineering limit, recent
history, a robust version of recent history, the same seasonal position, and the
peer group. The remaining two, expert judgement and upstream causality, enter
through parameters a human chooses.

Every function returns a (center, scale) pair on the caller's index so that a
deviation score is always `(x - center) / scale` regardless of which baseline
produced it. Keeping that shape uniform is what lets Lab 02 compare five
detectors on one axis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MAD_TO_SIGMA = 1.4826

# A deviation score is a ratio, and ratios explode when the denominator goes to
# zero. Capping keeps a plot readable, a severity model sane, and an alert table
# sortable. Anything at the cap should be read as "off the scale", not as a
# measurement.
MAX_SCORE = 50.0


def global_scale(values: pd.Series) -> float:
    """Robust spread of the whole series, with fallbacks for degenerate metrics."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    mad = float(np.median(np.abs(x - np.median(x)))) * MAD_TO_SIGMA
    if mad > 0:
        return mad
    std = float(np.std(x))
    if std > 0:
        return std
    return 0.01 * float(np.mean(np.abs(x)))


def scale_floor(values: pd.Series, fraction: float = 0.05) -> float:
    """Smallest denominator a deviation score is allowed to use.

    A quiet window has almost no spread, so any small movement divides by
    something close to zero. The floor has to be derived from the *spread* of
    the series, never from its level: a metric centred on 1000 with a spread of
    60 would otherwise be floored near 1000 and could never register a deviation
    at all.
    """
    spread = global_scale(values)
    return max(fraction * spread, 1e-12)


def degenerate_fraction(scale: pd.Series, values: pd.Series) -> float:
    """Share of samples where the scale estimate collapsed onto the floor.

    High here means the metric is near-constant and a normalised deviation
    carries no information about it. `error_rate` on a healthy link is the
    standard example: it is exactly zero almost always, so every window has zero
    spread and any nonzero reading scores as infinitely abnormal. Such a metric
    wants a fixed threshold on the raw count, not a z-score.
    """
    floor = scale_floor(values)
    return float((np.asarray(scale, dtype=float) <= floor * 1.0001).mean())


def _floor_scale(scale: pd.Series, values: pd.Series, fraction: float = 0.05) -> pd.Series:
    floor = scale_floor(values, fraction)
    return scale.fillna(floor).clip(lower=floor)


def fixed(values: pd.Series, center: float, scale: float) -> tuple[pd.Series, pd.Series]:
    """A hard engineering limit: link capacity, an SLO, a contractual bound."""
    return (
        pd.Series(center, index=values.index, dtype=float),
        pd.Series(scale, index=values.index, dtype=float),
    )


def rolling_mean(values: pd.Series, window: int, min_periods: int | None = None) -> tuple[pd.Series, pd.Series]:
    """Recent history via mean and standard deviation.

    Both statistics are pulled by the very anomaly they are meant to expose, so
    a sustained event longer than the window will drag the baseline up to meet
    it and the score will decay back towards zero.
    """
    min_periods = min_periods or max(3, window // 3)
    center = values.rolling(window, min_periods=min_periods).mean()
    scale = values.rolling(window, min_periods=min_periods).std()
    return center, _floor_scale(scale, values)


def rolling_robust(values: pd.Series, window: int, min_periods: int | None = None) -> tuple[pd.Series, pd.Series]:
    """Recent history via median and MAD.

    The median needs more than half the window to be contaminated before it
    moves, which buys tolerance against short spikes and against history that
    already contains unlabelled incidents.
    """
    min_periods = min_periods or max(3, window // 3)
    center = values.rolling(window, min_periods=min_periods).median()
    deviation = (values - center).abs()
    mad = deviation.rolling(window, min_periods=min_periods).median()
    return center, _floor_scale(mad * MAD_TO_SIGMA, values)


def _season_key(timestamps: pd.Series, by: str) -> pd.Series:
    if by == "hour":
        return timestamps.dt.hour.astype(str)
    if by == "daytype_hour":
        daytype = np.where(timestamps.dt.dayofweek >= 5, "weekend", "weekday")
        return pd.Series(daytype, index=timestamps.index) + "-" + timestamps.dt.hour.astype(str).str.zfill(2)
    if by == "dow_hour":
        return timestamps.dt.dayofweek.astype(str) + "-" + timestamps.dt.hour.astype(str).str.zfill(2)
    if by == "tod":
        return timestamps.dt.strftime("%H:%M")
    raise ValueError(f"Unknown seasonal key: {by}")


def seasonal(
    frame: pd.DataFrame,
    value_col: str,
    by: str = "daytype_hour",
    ts_col: str = "timestamp",
    train_mask: pd.Series | None = None,
    min_samples: int = 8,
) -> tuple[pd.Series, pd.Series]:
    """Same seasonal position: compare 10:00 Monday against other 10:00 weekdays.

    `train_mask` selects the rows the profile is estimated from. Excluding known
    incident windows is the difference between a baseline that describes normal
    operation and one that has quietly absorbed last month's outage.
    """
    values = frame[value_col].astype(float)
    key = _season_key(frame[ts_col], by)
    source = key if train_mask is None else key.where(train_mask)

    grouped = values.groupby(source, observed=True)
    center_map = grouped.median()
    mad_map = grouped.apply(lambda s: (s - s.median()).abs().median()) * MAD_TO_SIGMA
    counts = grouped.size()

    thin = counts[counts < min_samples].index
    center_map = center_map.drop(index=thin, errors="ignore")
    mad_map = mad_map.drop(index=thin, errors="ignore")

    center = key.map(center_map)
    scale = key.map(mad_map)
    center = center.fillna(values.median())
    return center, _floor_scale(scale, values)


def peer(
    frame: pd.DataFrame,
    value_col: str,
    ts_col: str = "timestamp",
    unit_col: str = "port_id",
    leave_one_out: bool = True,
) -> tuple[pd.Series, pd.Series]:
    """Peer group: judge a port against its siblings at the same instant.

    This is the only baseline here that survives a shift affecting the whole
    estate, and the only one blind to it. Two ports rising together look normal
    to a peer baseline and abnormal to every other baseline in this module,
    which is exactly the discrimination a broadcast storm needs.
    """
    wide = frame.pivot_table(index=ts_col, columns=unit_col, values=value_col, aggfunc="mean")
    matrix = wide.to_numpy(dtype=float)
    n_units = matrix.shape[1]

    centers = np.empty_like(matrix)
    scales = np.empty_like(matrix)
    for j in range(n_units):
        others = np.delete(matrix, j, axis=1) if (leave_one_out and n_units > 1) else matrix
        median = np.nanmedian(others, axis=1)
        mad = np.nanmedian(np.abs(others - median[:, None]), axis=1) * MAD_TO_SIGMA
        centers[:, j] = median
        scales[:, j] = mad

    center_wide = pd.DataFrame(centers, index=wide.index, columns=wide.columns)
    scale_wide = pd.DataFrame(scales, index=wide.index, columns=wide.columns)

    index = pd.MultiIndex.from_arrays([frame[ts_col], frame[unit_col]])
    center = pd.Series(center_wide.stack().reindex(index).to_numpy(), index=frame.index)
    scale = pd.Series(scale_wide.stack().reindex(index).to_numpy(), index=frame.index)
    return center, _floor_scale(scale, frame[value_col].astype(float))


def deviation_score(
    values: pd.Series,
    center: pd.Series,
    scale: pd.Series,
    signed: bool = True,
    cap: float = MAX_SCORE,
) -> pd.Series:
    """Normalised deviation, capped at +/- `cap`.

    Keep it signed unless the direction carries no meaning: a link that stops
    carrying traffic and a link that is saturated are both far from baseline and
    are not the same incident.
    """
    score = ((values - center) / scale).clip(lower=-cap, upper=cap)
    return score if signed else score.abs()
