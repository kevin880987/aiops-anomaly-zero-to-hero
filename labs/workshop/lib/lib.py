"""Plotting and scoring tools for the AIOps anomaly labs: palette, figure style, and the
ground-truth/plotting/scoring functions Lab 01 and Lab 02 both call.

Every function takes its data explicitly — `data`, `ports`, `columns`, `events` and similar have
no default. A bare `df` inside a function defined here would resolve against this file's own
namespace, not the caller's, so there is no notebook-level value to fall back to.
"""
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from cycler import cycler

# One colour means one thing everywhere: blue is the measured signal, orange the baseline or a
# ground-truth window, purple a derived score, red an alert or a limit. Green means inside
# expectation, which covers the band where no alert fires, a true positive, and the robust
# estimator that is the one holding up in its comparison.
C = {"signal": "#3B7DD8", "baseline": "#E0752D", "score": "#7A5AC7",
     "alert": "#D6455D", "truth": "#FF9F1C", "peer": "#2E9E7B", "band": "#2E9E7B",
     "muted": "#9AA4B0"}

# The band covers whole panels, so it is drawn far fainter than any line and faint enough to read
# a grid line through. Its legend swatch is a few centimetres square and would disappear at the
# same value, so the key is drawn stronger than the thing it names.
BAND_ALPHA, BAND_KEY_ALPHA = 0.10, 0.22

# The default cycle is the per-port palette, so a plot that draws several ports needs no colour
# argument at all. Distinct hues rather than a gradient: port identity is nominal.
PORT_C = ["#3B7DD8", "#E0752D", "#2E9E7B", "#7A5AC7", "#B04A6E"]

# The three outcomes a single sample can be marked with, one colour and one marker each, fixed
# here so green never means anything but a hit in any figure of either lab. TN has no entry
# because it is the line itself: it is the overwhelming majority of any month, and marking it
# would bury the three classes that carry the argument.
CONF = {"TP": ("#2E9E7B", "o"), "FP": ("#D6455D", "o"), "FN": ("#7A5AC7", "x")}
CONF_LABEL = {"TP": "TP  alert inside an anomaly",
              "FP": "FP  alert outside every anomaly",
              "FN": "FN  anomaly sample, no alert"}

# For the figures that draw one curve per (baseline, column): colour carries the baseline and the
# dash pattern carries the column, so nine curves stay readable without nine colours.
BASELINE_C = ["#3B7DD8", "#2E9E7B", "#7A5AC7"]
COLUMN_LS = ["-", "--", ":"]

# A heatmap encodes magnitude, so it takes one hue running light to dark rather than a rainbow: a
# reader has to be able to say "darker means more" without consulting a key. Blues is the same hue
# as C["signal"], so the sequential ramp and the measured line belong to one palette.
CMAP_SEQ = "Blues"


def set_figure_style():
    """The one figure style both labs draw with. Call once, right after import."""
    plt.rcParams.update({
        "figure.dpi": 110,
        "figure.figsize": (14, 4.6),
        "font.family": "serif",
        "font.size": 14,
        "axes.titlesize": 16, "axes.titlelocation": "left", "axes.titleweight": "bold",
        "axes.labelsize": 14,
        "legend.fontsize": 12,
        "xtick.labelsize": 13, "ytick.labelsize": 13,
        "figure.titlesize": 18,
        "lines.linewidth": 1.4, "lines.markersize": 7,
        "scatter.edgecolors": "white",
        "axes.prop_cycle": cycler(color=PORT_C),
        "axes.grid": True, "grid.alpha": 0.25,
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.autolayout": True,          # every figure is tight_layout by default
    })
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 80)


def anomaly_windows(data, events, ports):
    """Ground-truth (start, end) per anomaly and port. Pass "all" to drop a filter."""
    w = data[data["event_label"] != "normal"]
    if events != "all":
        w = w[w["event_label"].isin(events)]
    if ports != "all":
        w = w[w["port_id"].isin(ports)]
    return (w.groupby(["event_id", "event_label", "port_id"], as_index=False)
             .agg(start=("timestamp", "min"), end=("timestamp", "max"), n=("timestamp", "size"))
             .rename(columns={"event_label": "event_type"})
             .sort_values("start").reset_index(drop=True))


def legend_for(ports, alerts=None, baselines=None, smoothed=None, bands=None, outcomes=False):
    """Proxy handles for one figure, and the column count the figure width holds.

    Returns (handles, ncol). A legend column is as wide as its widest entry, so the widest are
    packed first and the count is the most that still fits.
    """
    handles = [plt.Line2D([], [], color=PORT_C[k % len(PORT_C)], label=pid[-4:])
               for k, pid in enumerate(ports)]
    handles.append(plt.Rectangle((0, 0), 1, 1, color=C["truth"], alpha=0.25,
                                 label="anomaly (ground truth)"))
    if bands is not None:
        handles.append(plt.Rectangle((0, 0), 1, 1, color=C["band"], alpha=BAND_KEY_ALPHA,
                                     label="no alert inside this band"))
    if baselines is not None:
        handles.append(plt.Line2D([], [], ls="--", color=C["baseline"], label="baseline"))
    # A smoothed signal is the signal, so its proxy is grey and its stroke is the encoding: the
    # hue on the figure stays the port's. A baseline is a different series and keeps its own hue.
    if smoothed is not None:
        handles.append(plt.Line2D([], [], ls="-", lw=2.8, color=C["muted"],
                                  label="smoothed signal"))
    if alerts is not None and outcomes:
        handles += [plt.Line2D([], [], linestyle="none", marker=marker, color=colour,
                               label=CONF_LABEL[kind]) for kind, (colour, marker) in CONF.items()]
    elif alerts is not None:
        handles.append(plt.Line2D([], [], linestyle="none", marker="o", color=C["alert"],
                                  label="alert"))

    # Entry width in em: handle and padding, plus text at roughly 0.6 em per character.
    em = sorted((2.6 + 0.6 * len(a.get_label()) for a in handles), reverse=True)
    avail = plt.rcParams["figure.figsize"][0] * 0.94 * 72 / plt.rcParams["legend.fontsize"]
    ncol = max((n for n in range(1, len(em) + 1) if sum(em[:n]) <= avail), default=1)
    return handles, ncol


def plot_signals(data, columns, ports, events, half, alerts=None,
                 baselines=None, smoothed=None, bands=None, outcomes=False, by_port=False,
                 pad="6h", title=None, zoom_anomaly=False, zoom_signal=False):
    """One panel per column, one line per port, ground truth shaded, alerts marked.

    `half` widens every ground-truth shade by this much on each side: a sample stamped 11:30
    stands for the interval ending there, not an instant, so shading from first timestamp to last
    would leave half a bucket unshaded at either end. Pass `pd.Timedelta(seconds=cadence / 2)`.

    `alerts`, `baselines` and `smoothed` are each a Series or a dict {column: Series}. Drawing the
    baseline over the signal is the only way to see a rolling baseline being dragged upward by the
    event it is supposed to be judging.

    `baselines` and `smoothed` are two different objects and are drawn differently on purpose.
    A baseline is a *reference*: a separate series, built from earlier samples only, that the
    signal is scored against. A smoothed signal is *the signal*, filtered — usually centred, so
    it uses the future and no online detector can have it. Passing one where the other belongs
    is the mistake this split exists to prevent, since the two look identical on a chart and
    behave nothing alike. A baseline gets its own hue and a dashed stroke. A smoothed line keeps
    its port's hue, because it is that port's series, and the raw line dims underneath it.

    `bands` is a (lower, upper) pair, or a dict {column: (lower, upper)}, drawn as a translucent
    fill. Each side is a Series or a plain number. This is the alert threshold in the units of
    the signal itself: pass `(centre - THRESHOLD * scale, centre + THRESHOLD * scale)` for a
    baseline detector, or `(0, LIMITS[col])` for a fixed one. A score above the cutoff and a
    sample outside the band are the same event, so the band shows how close a quiet sample was
    to firing, which a marker on an alert cannot.

    outcomes=False marks every alert the same way, which answers "where did it fire".
    outcomes=True
    splits each sample into TP, FP or FN and prints the counts in the panel title, which answers
    "was it right". A sample is positive when it falls inside an anomaly window on that port, on
    exactly the accounting `report` uses, so the figure and the table never disagree. TN is the
    line itself and is not marked.

    by_port=False overlays every port in one panel per column, which is the compact view and the
    default. by_port=False gives each port its own panel, stacked vertically, so each gets its own
    y-scale and its own TP/FP/FN count. Use it when the ports differ by more than the plot can
    show at one scale, or when a per-port baseline is the thing being examined.

    The two zooms are one per axis and both default off.

    zoom_anomaly=True narrows the x-range to the events in `events` plus `pad`, for the figures
    whose argument depends on seeing individual samples. Off, the range is the whole month, which
    is where stray alerts away from any event are visible.

    zoom_signal=False sets the y-range from the signal alone, so a baseline or a band that runs far
    outside it is clipped rather than obeyed. Off, the axis holds everything drawn on it, which is
    the honest default: a band taller than the panel is a fact about the detector, and hiding it by
    default would hide the detector going blind.
    """
    t0, t1 = data["timestamp"].min(), data["timestamp"].max()
    # `events` chooses what to zoom to; the shading always covers every anomaly window on the
    # drawn ports. Shading only the selected types would leave a red dot sitting on blank
    # background that `report` had already counted as a true positive.
    zoom_to = anomaly_windows(data, events, ports)
    win = anomaly_windows(data, "all", ports)
    if zoom_anomaly and len(zoom_to) and events != "all":
        pad = pd.Timedelta(pad)
        t0, t1 = zoom_to["start"].min() - pad, zoom_to["end"].max() + pad
    spread = lambda x: None if x is None else (x if isinstance(x, dict)
                                               else {c: x for c in columns})
    alerts, baselines = spread(alerts), spread(baselines)
    smoothed, bands = spread(smoothed), spread(bands)
    side = lambda b, idx: (pd.Series(float(b), index=idx) if np.isscalar(b) else b.loc[idx])

    # One panel per column, or one per (column, port) when by_port.
    panels = ([(c, [p]) for c in columns for p in ports] if by_port
              else [(c, ports) for c in columns])
    tally = [{"TP": 0, "FP": 0, "FN": 0} for _ in panels]

    h = plt.rcParams["figure.figsize"][1] * (0.50 if by_port else 0.72)
    fig, axes = plt.subplots(len(panels), 1,
                             figsize=(plt.rcParams["figure.figsize"][0], h * len(panels)),
                             sharex=True, squeeze=False, layout="constrained")
    take = lambda pid: data.loc[(data["port_id"] == pid) & data["timestamp"].between(t0, t1)]
    for i, (ax, (col, shown)) in enumerate(zip(axes[:, 0], panels)):
        # Pass one draws only the signal and the markers that sit on it, so the y-range after it
        # is the signal's own. Baselines and bands come after, and zoom_signal decides whether
        # they are allowed to widen it.
        for pid in shown:
            g = take(pid)
            # Colour follows the port, not the panel, so a port keeps its colour when by_port
            # restarts the cycle on every axes.
            # Markers on a short view, because a line between two samples crosses the window
            # edge and makes the signal look as if it moved before the event did.
            ax.plot(g["timestamp"], g[col], marker="." if len(g) <= 300 else None,
                    color=PORT_C[ports.index(pid) % len(PORT_C)], label=pid[-4:],
                    # Dimmed only when a smoothed version of this same series sits on top of it,
                    # so the eye reads the pair as one series before and after the filter.
                    alpha=0.40 if (smoothed is not None and col in smoothed) else 1.0)
            # Pass one, with the raw line, because a filtered signal is still the signal: it is
            # bounded by the data it came from, so it belongs inside the span zoom_signal freezes.
            if smoothed is not None and col in smoothed:
                ax.plot(g["timestamp"], smoothed[col].loc[g.index], ls="-", lw=2.8,
                        color=PORT_C[ports.index(pid) % len(PORT_C)])
            if alerts is None or col not in alerts:
                continue
            fired = alerts[col].loc[g.index].fillna(False).to_numpy()
            if not outcomes:
                ax.scatter(g.loc[fired, "timestamp"], g.loc[fired, col],
                           color=C["alert"], zorder=5)
                continue
            # positive means inside an anomaly window on this port, the same rule report uses
            pos = np.zeros(len(g), bool)
            for e in win[win["port_id"] == pid].itertuples():
                pos |= g["timestamp"].between(e.start, e.end).to_numpy()
            for kind, m in (("TP", fired & pos), ("FP", fired & ~pos), ("FN", ~fired & pos)):
                colour, marker = CONF[kind]
                ax.plot(g.loc[m, "timestamp"], g.loc[m, col], linestyle="none",
                        marker=marker, color=colour, zorder=5)
                tally[i][kind] += int(m.sum())

        signal_span = ax.get_ylim()
        for pid in shown:
            g = take(pid)
            if baselines is not None and col in baselines:
                ax.plot(g["timestamp"], baselines[col].loc[g.index], ls="--", color=C["baseline"])
            if bands is not None and col in bands:
                lower, upper = bands[col]
                ax.fill_between(g["timestamp"], side(lower, g.index), side(upper, g.index),
                                color=C["band"], alpha=BAND_ALPHA, lw=0, zorder=0)
        if zoom_signal:
            ax.set_ylim(*signal_span)

        for e in win[win["port_id"].isin(shown)].itertuples():
            ax.axvspan(max(e.start - half, t0), min(e.end + half, t1),
                       color=C["truth"], alpha=0.25, lw=0)
        ax.set_ylabel(f"{col}\n{shown[0][-4:]}" if by_port else col)
        if outcomes and alerts is not None and col in alerts:
            ax.set_title("  ".join(f"{k} {v}" for k, v in tally[i].items()))

    # Placed outside the axes, so it can never cover a sample. Reserving headroom inside the
    # panel is the version this replaces: it cost the figure height whether the legend needed it
    # or not, and on a narrow view it still landed on the markers the panel exists to show.
    handles, ncol = legend_for(ports=ports, alerts=alerts, baselines=baselines,
                               smoothed=smoothed, bands=bands, outcomes=outcomes)
    fig.legend(handles=handles, labels=[a.get_label() for a in handles], ncol=ncol,
               loc="outside lower center", framealpha=0.9, columnspacing=1.1,
               handletextpad=0.5)
    axes[-1, 0].set_xlim(t0, t1)
    axes[-1, 0].tick_params(axis="x", labelrotation=20)
    fig.suptitle(title or f"{', '.join(ports)}  |  {events}")
    plt.show()


def heatmap(frame, title=None, fmt="{:.2f}", ax=None, cmap=None, cbar_label="", log=False,
            annotate=None):
    """A sweep result as an annotated matrix: rows and columns from the frame, shade from value.

    Every sweep in either lab produces a small grid of numbers, and a grid of numbers is read one
    cell at a time while a grid of shades is read in one look. The values stay printed on the
    cells, because a sweep here ends in a chosen parameter and choosing needs the number rather
    than the ranking.

    One hue, light to dark, so darker always means more. Direction is named in the title rather
    than encoded, because "more" is good on a recall grid and bad on an alerts-per-day grid and no
    colour convention survives both.

    log=True puts the ramp on a log scale, for a grid whose largest value is two decades above its
    typical one. On a linear ramp that grid is one dark cell and thirty white ones, which encodes
    the outlier and nothing else.
    """
    cmap = CMAP_SEQ if cmap is None else cmap
    v = frame.to_numpy(dtype=float)
    own = ax is None
    if own:
        # Width from the number of columns, because a label that does not fit is a label nobody
        # reads. Height from the number of rows, for the same reason.
        _, ax = plt.subplots(figsize=(1.30 * frame.shape[1] + 2.6, 0.42 * len(frame) + 2.2))
    norm = None
    if log:
        floor = np.nanmin(v[v > 0]) if (v > 0).any() else 1.0
        norm = matplotlib.colors.LogNorm(vmin=floor, vmax=max(np.nanmax(v), floor * 10))
        v_shown = np.where(v > 0, v, floor)
        im = ax.imshow(v_shown, cmap=cmap, aspect="auto", norm=norm)
    else:
        im = ax.imshow(v, cmap=cmap, aspect="auto")
    ax.set_xticks(range(frame.shape[1]), [str(c) for c in frame.columns],
                  rotation=30, ha="right")
    ax.set_yticks(range(frame.shape[0]), [str(i) for i in frame.index])
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.grid(False)

    # Annotation ink is text ink, never the ramp: black on the pale cells, white on the dark ones.
    # Numbers on the cells while they still fit. A 7x24 grid annotated is a wall of digits, and
    # the shape is the whole point of drawing it that large.
    if annotate is None:
        annotate = frame.size <= 60
    shade = im.norm(im.get_array())          # 0..1 in the ramp, whatever the norm is
    for i in range(frame.shape[0]) if annotate else ():
        for j in range(frame.shape[1]):
            if np.isnan(v[i, j]):
                continue
            ax.text(j, i, fmt.format(v[i, j]), ha="center", va="center",
                    fontsize=plt.rcParams["legend.fontsize"] - 1,
                    color="white" if shade[i, j] > 0.6 else "#1B1F24")
    if title:
        ax.set_title(title)
    if own:
        plt.colorbar(im, ax=ax, label=cbar_label, fraction=0.04, pad=0.03)
        plt.show()
    return ax


def plot_ranked(score, threshold, name="score", ax=None):
    """Scores sorted high to low with the cutoff drawn across them.

    A cutoff sitting in a gap survives being moved. One inside a dense band splits
    near-identical samples on nothing.
    """
    s = pd.Series(score).dropna().sort_values(ascending=False).to_numpy()
    over = s > threshold
    rank = np.arange(1, len(s) + 1)
    own = ax is None
    if own:
        _, ax = plt.subplots()
    ax.plot(rank[~over], s[~over], "o", color=C["signal"], label="normal")
    ax.plot(rank[over], s[over], "o", color=C["alert"], label=f"anomaly ({over.sum()})")
    ax.axhline(threshold, color=C["alert"], ls="--", label=f"cutoff {threshold:g}")
    ax.set(xscale="log", xlabel="rank (log)", ylabel=name, title=name)
    ax.legend()
    if own:
        plt.show()


def report(alerts, data, ports, events="all"):
    """One row per detector, on the numbers a duty roster is actually built from.

    precision       share of alerts that landed inside an anomaly window
    anomaly_recall    windows with at least one alert inside them, over all windows. An incident
                    lasting an hour does not need every minute flagged, only one.
    delay_min       median minutes from a window's start to its first alert
    alerts_per_day  alerts outside every anomaly window, divided by the days on record

    The days-on-record denominator is the span of `data` itself, so it always matches whatever
    frame was passed in.

    Accuracy is deliberately absent: a fleet running at a normal base rate scores over 99% by
    alerting on nothing.
    """
    sub = data[data["port_id"].isin(ports)] if ports != "all" else data
    days = (sub["timestamp"].max() - sub["timestamp"].min()).total_seconds() / 86400
    win = anomaly_windows(sub, events, ports)
    inside = np.zeros(len(sub), bool)
    for e in win.itertuples():
        inside |= ((sub["port_id"] == e.port_id)
                   & sub["timestamp"].between(e.start, e.end)).to_numpy()

    rows = []
    for name, a in alerts.items():
        a = a.loc[sub.index].fillna(False).to_numpy()
        caught, delays = 0, []
        for e in win.itertuples():
            m = ((sub["port_id"] == e.port_id)
                 & sub["timestamp"].between(e.start, e.end)).to_numpy()
            if (a & m).any():
                caught += 1
                delays.append((sub.loc[a & m, "timestamp"].min() - e.start).total_seconds() / 60)
        rows.append({"detector": name, "alerts": int(a.sum()),
                     "precision": round(float((a & inside).sum() / a.sum()), 3) if a.sum() else np.nan,
                     "anomaly_recall": f"{caught}/{len(win)}",
                     "delay_min": round(float(np.median(delays)), 1) if delays else np.nan,
                     "alerts_per_day": round(float((a & ~inside).sum()) / days, 2)})
    return pd.DataFrame(rows)


def confirm(breach, data, n):
    """A breach becomes a label only after n of them in a row on the same port."""
    label = breach.fillna(False)
    for k in range(1, n):
        label &= breach.groupby(data["port_id"]).shift(k).fillna(False)
    return label


def sliding_windows(x, n_input):
    """Rows of `n_input` consecutive values. Row i ends at sample i + n_input - 1. A view."""
    return np.lib.stride_tricks.sliding_window_view(np.asarray(x, dtype=float), n_input)


def series_of(port, col, data, events, resid_col=None):
    """One port as a time-ordered frame with `value`, a boolean `target`, and optionally `resid`.

    `target` is True on the event types in `events`, which is what every representation is
    measured against. The index is reset, so a numpy array of the same length aligns.

    `resid_col`, when given, is read into a `resid` column — Lab 01's deseasonalised value, never
    recomputed here. Omit it for a call that has no use for the residual representation.
    """
    g = data[data["port_id"] == port].sort_values("timestamp").reset_index(drop=True)
    out = g.assign(value=g[col], target=g["event_label"].isin(events))
    if resid_col is not None:
        out = out.assign(resid=g[resid_col].fillna(0.0))
    return out


def apply_scaler(values, mean, scale):
    """(values - mean) / scale, as the one place both labs run this transform."""
    return (np.asarray(values, dtype=float) - mean) / scale


def evaluate(name, port, score, target, budget):
    """Alert on the top `budget` share of one score, then count hits against `target`.

    Cutting every method at the same budget is what makes them comparable: a matrix-profile
    distance and an IsolationForest score do not live on the same axis, and only equal alert
    counts put them on one.
    """
    s = pd.Series(score, dtype=float)
    thr = np.nanquantile(s.dropna(), budget)
    a = (s > thr).fillna(False).to_numpy()
    t = np.asarray(target, bool)[:len(a)]
    return {"port": port[-4:], "method": name, "alerts": int(a.sum()),
            "caught": int((a & t).sum()), "of": int(t.sum()),
            "precision": round(float((a & t).sum() / a.sum()), 3) if a.sum() else np.nan}


