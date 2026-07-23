"""One panel definition, rendered wherever it is needed.

Grafana is the visualization surface for this workshop. Cadets read results on a
dashboard, not in notebook output, because that is where they will read them at
work and because a chart you can only see next to the code that made it is not
an operational artefact.

A panel is declared once as a `PanelSpec`. `to_grafana` is the primary renderer.
`render` draws the same spec in matplotlib and exists as an offline fallback for
a laptop where Grafana will not start; the workshop labs do not use it.

The spec also declares which columns it needs, which is what `grafana.publish`
uses to decide what to send to Prometheus. Adding a series to a panel therefore
adds it to the export as well, with no second place to update and no way for the
dashboard to ask for a column nobody published.

All chart text stays in English: the notebooks run on three operating systems
and a missing CJK glyph renders as a box.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiops_contract as _contract  # noqa: E402

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

# Grafana unit ids, kept next to the human label so the notebook axis and the
# dashboard axis cannot disagree about what the number means.
UNITS = {
    "bytes_per_sec": ("Bps", "bytes/s"),
    "megabytes_per_sec": ("MBs", "MB/s"),
    "packets_per_sec": ("pps", "packets/s"),
    "ratio": ("percentunit", "ratio"),
    "bytes": ("bytes", "bytes"),
    "sigma": ("none", "deviation (sigma)"),
    "count": ("short", "count"),
    "minutes": ("m", "minutes"),
    "none": ("none", ""),
}

PALETTE = {
    "signal": "#3B7DD8",
    "baseline": "#E0752D",
    "band": "#E0752D",
    "score": "#7A5AC7",
    "alert": "#D6455D",
    "truth": "#7C8A99",
    "peer": "#2E9E7B",
    "muted": "#9AA4B0",
}


@dataclass
class Series:
    """One line on the panel."""

    column: str
    legend: str = ""
    color: str = PALETTE["signal"]
    kind: str = "line"          # line | points | dashed
    width: float = 1.2
    alpha: float = 1.0
    display_scale: float = 1.0  # divide the raw value for display, e.g. 1e6 for MB/s
    grafana_legend: str | None = None

    def label(self) -> str:
        return self.legend or self.column


@dataclass
class Band:
    """A shaded region between two columns, typically baseline +/- k*scale."""

    lower: str
    upper: str
    legend: str = "expected range"
    color: str = PALETTE["band"]
    alpha: float = 0.16


@dataclass
class ThresholdLine:
    value: float
    legend: str = ""
    color: str = PALETTE["alert"]


@dataclass
class PanelSpec:
    """A chart that exists identically in the notebook and on the dashboard."""

    title: str
    series: list[Series] = field(default_factory=list)
    band: Band | None = None
    thresholds: list[ThresholdLine] = field(default_factory=list)
    markers: str | None = None        # boolean column drawn as points on series[0]
    shade: str | None = None          # boolean column drawn as vertical shading
    unit: str = "none"
    kind: str = "timeseries"          # timeseries | state
    height: int = 8                   # Grafana grid rows
    width: int = 24                   # Grafana grid columns, 24 is full width
    description: str = ""

    def columns(self) -> list[str]:
        """Every dataframe column this panel reads."""
        names = [s.column for s in self.series]
        if self.band:
            names += [self.band.lower, self.band.upper]
        if self.markers:
            names.append(self.markers)
        if self.shade:
            names.append(self.shade)
        seen: list[str] = []
        for name in names:
            if name not in seen:
                seen.append(name)
        return seen

    def y_label(self) -> str:
        return UNITS.get(self.unit, ("none", ""))[1]


# ---------------------------------------------------------------------------
# matplotlib backend
# ---------------------------------------------------------------------------

def render(spec: PanelSpec, frame: pd.DataFrame, ax=None, ts_col: str = "timestamp"):
    """Draw the panel into the notebook."""
    if ax is None:
        _, ax = plt.subplots(figsize=(13, 3.4))

    time = frame[ts_col]
    scale = spec.series[0].display_scale if spec.series else 1.0

    if spec.shade and spec.shade in frame.columns:
        _shade_runs(ax, time, frame[spec.shade].fillna(False).to_numpy(dtype=bool))

    if spec.band and spec.band.lower in frame.columns and spec.band.upper in frame.columns:
        ax.fill_between(
            time,
            frame[spec.band.lower] / scale,
            frame[spec.band.upper] / scale,
            color=spec.band.color, alpha=spec.band.alpha, linewidth=0,
            label=spec.band.legend, zorder=1,
        )

    for item in spec.series:
        if item.column not in frame.columns:
            continue
        values = frame[item.column] / item.display_scale
        if item.kind == "points":
            ax.plot(time, values, ".", color=item.color, alpha=item.alpha,
                    markersize=item.width * 3, label=item.label(), zorder=3)
        else:
            ax.plot(time, values, color=item.color, linewidth=item.width, alpha=item.alpha,
                    linestyle="--" if item.kind == "dashed" else "-",
                    label=item.label(), zorder=3)

    if spec.markers and spec.markers in frame.columns and spec.series:
        hit = frame[frame[spec.markers].fillna(False).astype(bool)]
        if len(hit):
            ax.scatter(hit[ts_col], hit[spec.series[0].column] / scale,
                       s=26, color=PALETTE["alert"], zorder=5, edgecolors="none",
                       label=f"{spec.markers} ({len(hit)})")

    for line in spec.thresholds:
        ax.axhline(line.value, color=line.color, linestyle="--", linewidth=1.0,
                   alpha=0.85, label=line.legend or f"threshold {line.value:g}", zorder=2)

    ax.set_title(spec.title, fontsize=11, loc="left")
    ax.set_ylabel(spec.y_label(), fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.grid(True, alpha=0.22, linewidth=0.6)
    ax.legend(fontsize=8, loc="upper left", ncol=3, framealpha=0.85)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return ax


def _shade_runs(ax, time: pd.Series, mask) -> None:
    """Vertical shading for contiguous True runs, one legend entry for all."""
    import numpy as np

    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return
    splits = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[idx[0]], idx[splits + 1]])
    ends = np.concatenate([idx[splits], [idx[-1]]])
    for n, (a, b) in enumerate(zip(starts, ends)):
        ax.axvspan(time.iloc[a], time.iloc[b], color=PALETTE["truth"], alpha=0.18,
                   linewidth=0, zorder=0, label="ground truth" if n == 0 else None)


def render_stack(specs: list[PanelSpec], frame: pd.DataFrame, ts_col: str = "timestamp", height: float = 3.2):
    """Render several panels as a shared-x column, the notebook twin of a dashboard."""
    fig, axes = plt.subplots(len(specs), 1, figsize=(13, height * len(specs)), sharex=True)
    if len(specs) == 1:
        axes = [axes]
    for spec, ax in zip(specs, axes):
        render(spec, frame, ax=ax, ts_col=ts_col)
    fig.tight_layout()
    return fig, axes


# ---------------------------------------------------------------------------
# Grafana backend
# ---------------------------------------------------------------------------

# One owner for this name; the exporter reads the same module.
METRIC = _contract.RESULT_METRIC


def _expr(column: str, selector: dict | None = None) -> str:
    """Build the selector, using regex match for any Grafana template variable.

    Grafana interpolates a multi-value or All variable as an alternation such as
    `a|b|c`. Against the equality operator that is one literal string containing
    pipes, which matches nothing, so a dashboard opened on its default All value
    shows empty panels and looks exactly like a broken exporter.
    """
    parts = [f'column="{column}"']
    for key, value in (selector or {}).items():
        operator = "=~" if str(value).startswith("$") else "="
        parts.append(f'{key}{operator}"{value}"')
    return f"{METRIC}{{{', '.join(parts)}}}"


def _target(column: str, ref_id: str, selector: dict | None, legend: str) -> dict:
    return {
        "refId": ref_id,
        "expr": _expr(column, selector),
        "legendFormat": legend,
        "editorMode": "code",
        "range": True,
    }


def to_grafana(spec: PanelSpec, datasource_uid: str, selector: dict | None = None,
               grid: dict | None = None, panel_id: int = 1) -> dict:
    """Translate the same spec into a Grafana panel."""
    unit_id = UNITS.get(spec.unit, ("none", ""))[0]
    datasource = {"type": "prometheus", "uid": datasource_uid}

    targets, overrides = [], []
    ref_ids = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    plotted = list(spec.series)
    if spec.band:
        plotted = [
            Series(spec.band.lower, f"{spec.band.legend} lower", spec.band.color, alpha=0.0),
            Series(spec.band.upper, f"{spec.band.legend} upper", spec.band.color, alpha=0.0),
        ] + plotted

    for item in plotted:
        legend = item.grafana_legend or item.label()
        targets.append(_target(item.column, next(ref_ids), selector, legend))
        custom = {"lineWidth": item.width, "fillOpacity": 0}
        if item.kind == "points":
            custom |= {"drawStyle": "points", "pointSize": 6}
        if item.kind == "dashed":
            custom |= {"lineStyle": {"fill": "dash", "dash": [8, 6]}}
        properties = [
            {"id": "color", "value": {"mode": "fixed", "fixedColor": item.color}},
            *[{"id": f"custom.{key}", "value": value} for key, value in custom.items()],
        ]
        overrides.append({"matcher": {"id": "byName", "options": legend}, "properties": properties})

    if spec.band:
        lower = f"{spec.band.legend} lower"
        upper = f"{spec.band.legend} upper"
        overrides.append({
            "matcher": {"id": "byName", "options": upper},
            "properties": [
                {"id": "custom.fillBelowTo", "value": lower},
                {"id": "custom.fillOpacity", "value": int(spec.band.alpha * 100)},
                {"id": "custom.lineWidth", "value": 0},
                {"id": "color", "value": {"mode": "fixed", "fixedColor": spec.band.color}},
            ],
        })
        overrides.append({
            "matcher": {"id": "byName", "options": lower},
            "properties": [{"id": "custom.lineWidth", "value": 0},
                           {"id": "custom.hideFrom", "value": {"legend": True, "tooltip": False, "viz": False}}],
        })

    steps = [{"color": "transparent", "value": None}]
    for line in spec.thresholds:
        steps.append({"color": line.color, "value": line.value})

    if spec.kind == "state":
        panel_type = "state-timeline"
        options = {
            "showValue": "never",
            "mergeValues": True,
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
        }
    else:
        panel_type = "timeseries"
        options = {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True, "calcs": []},
            "tooltip": {"mode": "multi", "sort": "desc"},
        }

    return {
        "id": panel_id,
        "type": panel_type,
        "title": spec.title,
        "description": spec.description,
        "datasource": datasource,
        "gridPos": grid or {"h": spec.height, "w": spec.width, "x": 0, "y": 0},
        "targets": targets,
        "options": options,
        "fieldConfig": {
            "defaults": {
                "unit": unit_id,
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "linear",
                    "showPoints": "never",
                    "fillOpacity": 0,
                    "spanNulls": True,
                    "thresholdsStyle": {"mode": "line" if spec.thresholds else "off"},
                },
                "thresholds": {"mode": "absolute", "steps": steps},
            },
            "overrides": overrides,
        },
    }


def stat_panel(title: str, column: str, datasource_uid: str, unit: str = "none",
               selector: dict | None = None, grid: dict | None = None,
               panel_id: int = 1, decimals: int = 2, description: str = "",
               aggregate: str = "max") -> dict:
    """A single number: event recall, alerts per day, detection delay.

    Scalars are broadcast down every row when published, so the raw query returns
    one identical series per port. Aggregating collapses them back to the single
    figure the tile is supposed to show.
    """
    target = _target(column, "A", selector, title)
    if aggregate:
        target["expr"] = f"{aggregate}({target['expr']})"
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "description": description,
        "datasource": {"type": "prometheus", "uid": datasource_uid},
        "gridPos": grid or {"h": 4, "w": 4, "x": 0, "y": 0},
        "targets": [target],
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto", "colorMode": "value", "graphMode": "none", "justifyMode": "auto",
        },
        "fieldConfig": {
            "defaults": {
                "unit": UNITS.get(unit, ("none", ""))[0],
                "decimals": decimals,
                "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]},
            },
            "overrides": [],
        },
    }


def promql_panel(title: str, queries: list[tuple[str, str]], datasource_uid: str,
                 unit: str = "none", grid: dict | None = None, panel_id: int = 1,
                 kind: str = "timeseries", description: str = "",
                 thresholds: list[ThresholdLine] | None = None) -> dict:
    """A panel driven by arbitrary PromQL rather than by a published column.

    Needed for anything that never passes through a notebook: node_exporter
    metrics, exporter health, the replay clock.
    """
    targets = [
        {"refId": chr(65 + n), "expr": expr, "legendFormat": legend,
         "editorMode": "code", "range": kind != "stat", "instant": kind == "stat"}
        for n, (expr, legend) in enumerate(queries)
    ]
    steps = [{"color": "text", "value": None}]
    for line in (thresholds or []):
        steps.append({"color": line.color, "value": line.value})

    panel = {
        "id": panel_id,
        "type": kind,
        "title": title,
        "description": description,
        "datasource": {"type": "prometheus", "uid": datasource_uid},
        "gridPos": grid or {"h": 8, "w": 24, "x": 0, "y": 0},
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": UNITS.get(unit, ("none", ""))[0],
                "custom": ({"drawStyle": "line", "lineWidth": 1.4, "fillOpacity": 6,
                            "showPoints": "never", "spanNulls": True,
                            "thresholdsStyle": {"mode": "line" if thresholds else "off"}}
                           if kind == "timeseries" else {}),
                "thresholds": {"mode": "absolute", "steps": steps},
            },
            "overrides": [],
        },
    }
    if kind == "stat":
        panel["options"] = {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto", "colorMode": "value", "graphMode": "area",
        }
    elif kind == "gauge":
        panel["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}
    else:
        panel["options"] = {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        }
    return panel


def text_panel(title: str, content: str, panel_id: int, grid: dict) -> dict:
    """Instructions rendered on the dashboard itself.

    A cadet reading the dashboard should not have to hold the lab sheet in the
    other hand.
    """
    return {
        "id": panel_id, "type": "text", "title": title, "gridPos": grid,
        "options": {"mode": "markdown", "content": content},
    }


def row(title: str, panel_id: int, y: int) -> dict:
    return {
        "id": panel_id, "type": "row", "title": title, "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": [],
    }


def port_variable(datasource_uid: str) -> dict:
    """A dashboard dropdown listing every port present in the published result.

    Lets one dashboard serve five ports, which is the difference between a
    workshop artefact and something an operator would keep.
    """
    return {
        "name": "port",
        "label": "Port",
        "type": "query",
        "datasource": {"type": "prometheus", "uid": datasource_uid},
        "query": {"query": f"label_values({METRIC}, port_id)", "refId": "port"},
        "definition": f"label_values({METRIC}, port_id)",
        "refresh": 2,
        "includeAll": True,
        "multi": False,
        "sort": 1,
        "current": {"text": "All", "value": "$__all"},
    }


def dashboard(title: str, uid: str, panels: list[dict], tags: list[str] | None = None,
              time_from: str = "now-30m", refresh: str = "10s",
              variables: list[dict] | None = None, description: str = "") -> dict:
    """Assemble panels into an importable dashboard.

    The default window is relative because the drop-zone exporter replays the
    dataset against wall-clock time; an absolute range would show an empty chart.
    """
    return {
        "uid": uid,
        "title": title,
        "description": description,
        "tags": tags or ["aiops-workshop"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 0,
        "refresh": refresh,
        "editable": True,
        "templating": {"list": variables or []},
        "time": {"from": time_from, "to": "now"},
        "annotations": {"list": [{
            "builtIn": 1, "type": "dashboard", "hide": True,
            "name": "Annotations & Alerts", "iconColor": "rgba(0, 211, 255, 1)",
            "datasource": {"type": "grafana", "uid": "-- Grafana --"},
        }]},
        "panels": panels,
    }


def layout(specs: list[PanelSpec], datasource_uid: str, selector: dict | None = None,
           start_id: int = 1, start_y: int = 0) -> list[dict]:
    """Stack specs full width, in order, assigning grid positions and ids."""
    panels, y, panel_id = [], start_y, start_id
    for spec in specs:
        panels.append(to_grafana(
            spec, datasource_uid, selector=selector,
            grid={"h": spec.height, "w": spec.width, "x": 0, "y": y},
            panel_id=panel_id,
        ))
        y += spec.height
        panel_id += 1
    return panels
