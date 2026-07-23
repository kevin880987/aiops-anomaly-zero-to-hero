"""The wiring between a notebook result and a Grafana dashboard.

The path is deliberately the same one a production deployment uses, only
shortened: Python writes a result CSV, an exporter turns it into a Prometheus
metric, Prometheus scrapes it, Grafana queries Prometheus. Nothing here reads a
CSV from Grafana, because nothing in production would.

Three things live in this module:

  publish        put result columns on the wire
  GrafanaClient  create the datasource, upload dashboards, push annotations
  check_stack    tell a cadet which of the four services is not running

Everything degrades to a printed instruction when a service is unreachable, so a
lab still completes on a laptop with no Grafana installed.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from . import paths, viz

PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
EXPORTER_URL = "http://localhost:8010"
EXPORTER_JOB = viz._contract.EXPORTER_JOB

DEFAULT_LABELS = ["device_id", "port_id", "port_role", "event_label"]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _request(url: str, method: str = "GET", payload=None, auth: tuple | None = None,
             timeout: float = 6.0, headers: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data:
        request.add_header("Content-Type", "application/json")
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as error:
        # Grafana explains rejections in the response body; losing it turns
        # every misconfiguration into an unhelpful "400 Bad Request".
        detail = error.read().decode(errors="replace")[:600]
        raise RuntimeError(f"HTTP {error.code} {method} {url}: {detail}") from None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


# ---------------------------------------------------------------------------
# Publishing results
# ---------------------------------------------------------------------------

def publish(
    frame: pd.DataFrame,
    columns: list[str],
    name: str,
    labels: list[str] | None = None,
    scalars: dict | None = None,
    ts_col: str = "timestamp",
    quiet: bool = False,
) -> dict:
    """Send result columns down the drop-zone path.

    Writes two files. The archive under outputs/workshop keeps the lab result;
    the drop-zone copy is what the exporter watches. A manifest travels with it
    so the exporter publishes exactly these columns instead of guessing from
    whatever happens to be numeric.

    `scalars` are single values -- an event recall, an alerts-per-day figure --
    broadcast down every row so a Grafana stat panel can read them like any
    other series.
    """
    paths.ensure_dirs()
    labels = labels if labels is not None else [c for c in DEFAULT_LABELS if c in frame.columns]

    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise KeyError(f"publish: columns not in frame: {missing}")

    export = frame[[ts_col, *labels, *columns]].copy()
    for column in columns:
        # Prometheus gauges are floats; booleans become 1/0 so a state panel works.
        if export[column].dtype == bool:
            export[column] = export[column].astype(float)
    for key, value in (scalars or {}).items():
        export[key] = float(value)

    value_columns = list(columns) + list((scalars or {}).keys())
    archive = paths.OUTPUT_DIR / f"{name}.csv"
    export.to_csv(archive, index=False)
    export.to_csv(paths.DROPZONE_CSV, index=False)

    manifest = {
        "source": name,
        "value_columns": value_columns,
        "label_columns": labels,
        "rows": int(len(export)),
        "sim_start": str(export[ts_col].min()),
        "sim_end": str(export[ts_col].max()),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    paths.DROPZONE_MANIFEST.write_text(json.dumps(manifest, indent=2))

    if not quiet:
        print(f"published {len(export):,} rows as '{name}'")
        print(f"  archive   {archive.relative_to(paths.ROOT)}")
        print(f"  drop zone {paths.DROPZONE_CSV.relative_to(paths.ROOT)}")
        print(f"  columns   {', '.join(value_columns)}")
        print(f"  query     {viz.METRIC}{{column=\"{value_columns[0]}\"}}")
    return manifest


# ---------------------------------------------------------------------------
# Replay clock
# ---------------------------------------------------------------------------

@dataclass
class ReplayClock:
    """Maps dataset time onto wall-clock time.

    The exporter walks a month of telemetry faster than real time so that a
    dashboard has something moving on it during a three-hour class. Any
    annotation placed on that dashboard has to be mapped through the same
    function, or the marker for an incident lands nowhere near the spike.
    """

    wall_start: float
    sim_start: pd.Timestamp
    sim_end: pd.Timestamp
    speed_x: float

    @classmethod
    def load(cls) -> "ReplayClock | None":
        try:
            state = json.loads(paths.REPLAY_STATE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        return cls(
            wall_start=float(state["wall_start"]),
            sim_start=pd.Timestamp(state["sim_start"]),
            sim_end=pd.Timestamp(state["sim_end"]),
            speed_x=float(state["speed_x"]),
        )

    def span_s(self) -> float:
        return max((self.sim_end - self.sim_start).total_seconds(), 1.0)

    def to_wall(self, sim_ts: pd.Timestamp) -> pd.Timestamp:
        offset = (pd.Timestamp(sim_ts) - self.sim_start).total_seconds() / self.speed_x
        return pd.Timestamp(self.wall_start + offset, unit="s", tz="UTC").tz_convert(None)

    def pass_duration_min(self) -> float:
        return self.span_s() / self.speed_x / 60


# ---------------------------------------------------------------------------
# Grafana API
# ---------------------------------------------------------------------------

@dataclass
class GrafanaClient:
    url: str = GRAFANA_URL
    user: str = "admin"
    password: str = "admin"
    _datasource_uid: str | None = field(default=None, repr=False)

    def _auth(self) -> tuple:
        return (self.user, self.password)

    def healthy(self) -> bool:
        try:
            return _request(f"{self.url}/api/health").get("database") == "ok"
        except Exception:
            return False

    def prometheus_uid(self, create: bool = True) -> str | None:
        """Find the Prometheus datasource, creating it if the cadet has not."""
        if self._datasource_uid:
            return self._datasource_uid
        try:
            sources = _request(f"{self.url}/api/datasources", auth=self._auth())
        except Exception:
            return None
        for source in sources:
            if source.get("type") == "prometheus":
                self._datasource_uid = source["uid"]
                return self._datasource_uid
        if not create:
            return None
        try:
            created = _request(
                f"{self.url}/api/datasources", method="POST", auth=self._auth(),
                payload={"name": "Prometheus", "type": "prometheus", "url": PROMETHEUS_URL,
                         "access": "proxy", "isDefault": True},
            )
            self._datasource_uid = created["datasource"]["uid"]
            return self._datasource_uid
        except Exception:
            return None

    def upload(self, dashboard: dict, folder_uid: str | None = None) -> str | None:
        """Create or overwrite a dashboard. Returns its URL."""
        payload = {"dashboard": dashboard, "overwrite": True,
                   "message": "aiops workshop notebook"}
        if folder_uid:
            payload["folderUid"] = folder_uid
        try:
            result = _request(f"{self.url}/api/dashboards/db", method="POST",
                              auth=self._auth(), payload=payload)
            return f"{self.url}{result['url']}"
        except Exception:
            return None

    def annotate(self, items: list[dict], clear_tag: str | None = None) -> int:
        """Push region annotations. Each item needs time, timeEnd, text, tags."""
        if clear_tag:
            self.clear_annotations(clear_tag)
        pushed = 0
        for item in items:
            try:
                _request(f"{self.url}/api/annotations", method="POST", auth=self._auth(), payload=item)
                pushed += 1
            except Exception:
                continue
        return pushed

    def clear_annotations(self, tag: str) -> int:
        try:
            existing = _request(
                f"{self.url}/api/annotations?tags={urllib.parse.quote(tag)}&limit=500",
                auth=self._auth(),
            )
        except Exception:
            return 0
        removed = 0
        for annotation in existing:
            try:
                _request(f"{self.url}/api/annotations/{annotation['id']}", method="DELETE", auth=self._auth())
                removed += 1
            except Exception:
                continue
        return removed

    def explore_url(self, promql: str, minutes: int = 30) -> str:
        """A link that opens Grafana Explore with the query already typed in."""
        uid = self.prometheus_uid(create=False) or "prometheus"
        pane = {"aiops": {
            "datasource": uid,
            "queries": [{"refId": "A", "expr": promql, "datasource": {"type": "prometheus", "uid": uid}}],
            "range": {"from": f"now-{minutes}m", "to": "now"},
        }}
        query = urllib.parse.urlencode({"schemaVersion": 1, "orgId": 1, "panes": json.dumps(pane)})
        return f"{self.url}/explore?{query}"


def deploy(
    title: str,
    uid: str,
    specs: list[viz.PanelSpec],
    selector: dict | None = None,
    stats: list[dict] | None = None,
    annotation_tag: str | None = None,
    client: GrafanaClient | None = None,
    time_from: str = "now-30m",
    save: bool = True,
) -> dict:
    """Build a dashboard from panel specs, save it, and upload it if Grafana is up.

    Returns a dict with the JSON path and, when the upload succeeded, the URL.
    The dashboard file is written either way, so an offline cadet can still
    import it by hand later.
    """
    client = client or GrafanaClient()
    datasource_uid = client.prometheus_uid() or "prometheus"

    panels: list[dict] = []
    y, panel_id = 0, 1
    if stats:
        for n, stat in enumerate(stats):
            panels.append(viz.stat_panel(
                stat["title"], stat["column"], datasource_uid,
                unit=stat.get("unit", "none"), selector=selector,
                grid={"h": 4, "w": max(24 // len(stats), 3), "x": (24 // len(stats)) * n, "y": y},
                panel_id=panel_id, decimals=stat.get("decimals", 2),
                description=stat.get("description", ""),
            ))
            panel_id += 1
        y += 4

    panels += viz.layout(specs, datasource_uid, selector=selector, start_id=panel_id, start_y=y)

    dashboard = viz.dashboard(title, uid, panels, time_from=time_from)
    if annotation_tag:
        dashboard["annotations"]["list"].append({
            "name": annotation_tag,
            "enable": True,
            "iconColor": "rgba(214, 69, 93, 1)",
            "datasource": {"type": "grafana", "uid": "-- Grafana --"},
            "target": {"type": "tags", "matchAny": False, "tags": [annotation_tag], "limit": 200},
        })

    result = {"uid": uid, "title": title, "path": None, "url": None}
    if save:
        paths.ensure_dirs()
        path = paths.GRAFANA_DASHBOARD_DIR / f"{uid}.json"
        path.write_text(json.dumps(dashboard, indent=2))
        result["path"] = str(path.relative_to(paths.ROOT))

    result["url"] = client.upload(dashboard)
    if result["url"]:
        print(f"dashboard live: {result['url']}")
    else:
        print(f"Grafana not reachable at {client.url}.")
        print(f"  dashboard JSON saved to {result['path']}")
        print("  import later with Dashboards > New > Import > Upload JSON file")
    return result


def event_annotations(
    events: pd.DataFrame,
    tag: str,
    clock: ReplayClock | None = None,
    text_col: str = "event_type",
    extra_tags: list[str] | None = None,
) -> list[dict]:
    """Turn ground-truth windows or detected alerts into Grafana region annotations.

    Without a replay clock the sim timestamps are used unchanged, which is right
    when the dashboard is looking at a historical range and wrong when it is
    following a live replay.
    """
    clock = clock or ReplayClock.load()
    items = []
    for row in events.itertuples():
        start = getattr(row, "start", None) or getattr(row, "fire_time", None)
        end = getattr(row, "end", None) or getattr(row, "clear_time", None)
        if start is None or end is None:
            continue
        if clock:
            start, end = clock.to_wall(start), clock.to_wall(end)
        label = str(getattr(row, text_col, ""))
        port = str(getattr(row, "port_id", ""))
        items.append({
            "time": int(pd.Timestamp(start).timestamp() * 1000),
            "timeEnd": int(pd.Timestamp(end).timestamp() * 1000),
            "tags": [tag, *(extra_tags or []), port] if port else [tag, *(extra_tags or [])],
            "text": f"{label} on {port}" if port else label,
        })
    return items


# ---------------------------------------------------------------------------
# Stack check
# ---------------------------------------------------------------------------

def _prometheus_query(promql: str) -> list:
    url = f"{PROMETHEUS_URL}/api/v1/query?{urllib.parse.urlencode({'query': promql})}"
    return _request(url).get("data", {}).get("result", [])


def check_stack(verbose: bool = True) -> dict:
    """Report which parts of the path are live, and what to run for the rest."""
    status = {}

    try:
        _request(f"{PROMETHEUS_URL}/-/healthy", timeout=3)
        status["prometheus"] = "up"
    except Exception:
        status["prometheus"] = "down"

    try:
        _request(f"{EXPORTER_URL}/metrics", timeout=3)
        status["results_exporter"] = "up"
    except Exception:
        status["results_exporter"] = "down"

    client = GrafanaClient()
    status["grafana"] = "up" if client.healthy() else "down"
    status["grafana_datasource"] = client.prometheus_uid(create=False) or "missing"

    if status["prometheus"] == "up":
        try:
            targets = {
                series["metric"].get("job"): series["value"][1]
                for series in _prometheus_query("up")
            }
            status["scrape_targets"] = {job: ("up" if value == "1" else "down") for job, value in targets.items()}
            # Distinguishing "the job is down" from "the job is not in the config
            # at all" matters more than it looks. Starting Prometheus through a
            # package manager picks up that package's default config, which has
            # never heard of this exporter, and the failure presents as an empty
            # dashboard with every service apparently running.
            status["exporter_job_configured"] = EXPORTER_JOB in targets
            status["result_series"] = len(_prometheus_query(viz.METRIC))
        except Exception:
            status["scrape_targets"] = {}
            status["exporter_job_configured"] = False
            status["result_series"] = 0

    if verbose:
        print(f"{'component':<22}{'status':<10}detail")
        print("-" * 78)
        print(f"{'Prometheus':<22}{status['prometheus']:<10}{PROMETHEUS_URL}")
        print(f"{'results exporter':<22}{status['results_exporter']:<10}{EXPORTER_URL}/metrics")
        print(f"{'Grafana':<22}{status['grafana']:<10}{GRAFANA_URL}  datasource={status['grafana_datasource']}")
        for job, state in status.get("scrape_targets", {}).items():
            print(f"{'  scrape ' + str(job):<24}{state:<10}")
        if "result_series" in status:
            print(f"{'  ' + viz.METRIC:<24}{'':<10}{status['result_series']} series in Prometheus")
        print()
        for line in remediation(status):
            print(line)
    return status


def remediation(status: dict) -> list[str]:
    """Exactly the command to run for whatever is not working."""
    lines = []
    if status.get("prometheus") != "up":
        lines.append("start Prometheus:  prometheus --config.file=infra/prometheus/prometheus.macos.yml")
    elif not status.get("exporter_job_configured", True):
        lines.append(
            f"Prometheus is running but has no '{EXPORTER_JOB}' scrape job, so nothing you")
        lines.append(
            "  publish can reach Grafana. This happens when Prometheus was started from a")
        lines.append(
            "  package default config instead of the repository one. Stop it and restart with:")
        lines.append(
            "    prometheus --config.file=infra/prometheus/prometheus.macos.yml")
        lines.append(
            "  (use prometheus.linux.yml or prometheus.windows.yml as appropriate)")
    if status.get("results_exporter") != "up":
        lines.append("start exporter:    REPLAY_SPEED_X=720 python infra/python_results_exporter.py")
    if status.get("grafana") != "up":
        lines.append("start Grafana:     brew services start grafana   (macOS)")
        lines.append("                   sudo systemctl start grafana-server   (Linux)")
    if status.get("grafana") == "up" and status.get("grafana_datasource") == "missing":
        lines.append("wire up Grafana:   python infra/setup_grafana.py")
    if not lines:
        if status.get("result_series", 0) == 0:
            lines.append("all services up, but nothing has been published yet.")
            lines.append("  Run a workshop notebook through its publish step.")
        else:
            lines.append(
                f"all services up, {status.get('result_series')} result series in Prometheus.")
            lines.append("  Dashboards: http://localhost:3000/dashboards")
    return lines
