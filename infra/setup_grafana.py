#!/usr/bin/env python3
"""Provision the whole workshop into Grafana with one command.

    python infra/setup_grafana.py

Creates the Prometheus datasource, an "AIOps Workshop" folder, three
dashboards, three alert rules and a maintenance mute timing. Idempotent: run it
again after breaking something and it restores the starting state.

Everything is created *unprovenanced*, which means Grafana treats it as
hand-made and lets cadets edit it in the UI. That is the point. The script puts
a working example in front of them; the lab work is changing it through the
interface and watching what happens.

Options:
    --url, --user, --password    Grafana location and credentials
    --reset                      delete workshop objects before recreating
    --dry-run                    write dashboard JSON to disk, contact nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiopskit import paths, viz  # noqa: E402
from aiopskit.grafana import GrafanaClient, _request  # noqa: E402

FOLDER_UID = "aiops-workshop"
FOLDER_TITLE = "AIOps Workshop"
MUTE_TIMING = "aiops-maintenance-window"

# Prometheus anchors label regexes, so a bare "lo" matches only the exact string
# "lo" and lets macOS loopback "lo0" through. On an idle laptop lo0 can be the
# largest series on the panel, which is a confusing first thing to show someone.
PHYSICAL_IFACE = ('device!~"lo\\d*|docker.*|veth.*|br-.*|utun.*|bridge.*|awdl.*'
                  '|llw.*|gif.*|stf.*|anpi.*|ap[0-9].*"')


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

def lab00_dashboard(uid: str) -> dict:
    """Lab 00 proves the path works before any algorithm is discussed."""
    panels: list[dict] = []
    pid = 1

    panels.append(viz.text_panel(
        "What you are looking at", (
            "This dashboard answers one question: **does a number computed in Python reach this screen?**\n\n"
            "`notebook -> current_results.csv -> python_results_exporter :8010 -> Prometheus -> this panel`\n\n"
            "If the four tiles below are green and the toy signal moves, the path is open. "
            "Nothing later in the workshop works until it is."
        ), pid, {"h": 4, "w": 24, "x": 0, "y": 0}))
    pid += 1

    tiles = [
        ("Exporter up", 'up{job="python-results-exporter"}', "count",
         "1 means Prometheus is scraping the Python exporter. 0 means it is not running."),
        ("Rows loaded", "aiops_result_rows", "count",
         "Rows in the CSV the exporter is currently replaying."),
        ("Replay speed", "aiops_replay_speed_x", "count",
         "Simulated seconds advanced per real second."),
        ("Replay progress", "aiops_replay_progress", "ratio",
         "Position through the dataset. Wraps back to 0 and replays."),
    ]
    for n, (title, expr, unit, desc) in enumerate(tiles):
        panels.append(viz.promql_panel(
            title, [(expr, title)], uid, unit=unit, kind="stat", panel_id=pid,
            grid={"h": 4, "w": 6, "x": 6 * n, "y": 4}, description=desc))
        pid += 1

    panels.append(viz.promql_panel(
        "Toy signal published from the notebook",
        [('aiops_python_result{column="toy_value"}', "toy_value"),
         ('aiops_python_result{column="toy_baseline"}', "toy_baseline")],
        uid, unit="count", panel_id=pid, grid={"h": 9, "w": 24, "x": 0, "y": 8},
        description=("A sine wave with one injected step, computed in Python. "
                     "Change the amplitude in the notebook, republish, and this panel follows."),
        thresholds=[viz.ThresholdLine(85.0, "toy alert threshold")]))
    pid += 1

    panels.append(viz.promql_panel(
        "Your own machine: receive rate",
        [(f'rate(node_network_receive_bytes_total{{{PHYSICAL_IFACE}}}[1m])', "{{device}}")],
        uid, unit="bytes_per_sec", panel_id=pid, grid={"h": 9, "w": 12, "x": 0, "y": 17},
        description="Real metrics from node_exporter, for comparison with the replayed dataset."))
    pid += 1
    panels.append(viz.promql_panel(
        "Your own machine: transmit rate",
        [(f'rate(node_network_transmit_bytes_total{{{PHYSICAL_IFACE}}}[1m])', "{{device}}")],
        uid, unit="bytes_per_sec", panel_id=pid, grid={"h": 9, "w": 12, "x": 12, "y": 17}))

    return viz.dashboard(
        "Lab 00 - Pipeline check", "aiops-lab00", panels,
        tags=["aiops-workshop", "lab00"], time_from="now-15m", refresh="10s",
        description="Prove the Python to Grafana path before doing any analysis.")


def lab01_dashboard(uid: str) -> dict:
    """Lab 01 is about baselines: five answers to 'compared with what?'."""
    selector = {"port_id": "$port"}
    panels: list[dict] = []
    pid = 1

    panels.append(viz.text_panel(
        "Compared with what?", (
            "An observation is not abnormal on its own. It is abnormal relative to a **baseline**, "
            "and the baseline you choose decides what you can see.\n\n"
            "Each panel below is the same traffic against a different baseline. "
            "Use the **Port** dropdown to switch ports, and watch which baselines the "
            "shaded expected range follows and which it does not."
        ), pid, {"h": 4, "w": 24, "x": 0, "y": 0}))
    pid += 1

    specs = [
        viz.PanelSpec(
            title="Recent history: 1h rolling mean, +/- 3 sigma",
            description=("The mean and standard deviation are pulled by the anomaly they are "
                         "meant to expose. Watch the band swell to swallow a long event."),
            series=[viz.Series("traffic_bps", "traffic", display_scale=1e6),
                    viz.Series("roll_center", "rolling mean", color=viz.PALETTE["baseline"], display_scale=1e6)],
            band=viz.Band("roll_lo", "roll_hi", "rolling +/-3 sigma"),
            unit="megabytes_per_sec", height=8),
        viz.PanelSpec(
            title="Recent history, robust: 1h rolling median, +/- 3 MAD",
            description=("The median needs more than half the window contaminated before it moves. "
                         "Compare the band width against the panel above during an event."),
            series=[viz.Series("traffic_bps", "traffic", display_scale=1e6),
                    viz.Series("robust_center", "rolling median", color=viz.PALETTE["baseline"], display_scale=1e6)],
            band=viz.Band("robust_lo", "robust_hi", "robust +/-3 MAD"),
            unit="megabytes_per_sec", height=8),
        viz.PanelSpec(
            title="Same seasonal position: this hour, on days like today",
            description=("Compares 10:00 Monday against other 10:00 weekdays instead of against "
                         "10:00 today. The only baseline here that knows the traffic is supposed to rise."),
            series=[viz.Series("traffic_bps", "traffic", display_scale=1e6),
                    viz.Series("seasonal_center", "seasonal median", color=viz.PALETTE["baseline"], display_scale=1e6)],
            band=viz.Band("seasonal_lo", "seasonal_hi", "seasonal +/-3 MAD"),
            unit="megabytes_per_sec", height=8),
        viz.PanelSpec(
            title="Peer group: this port against its siblings, same instant",
            description=("Blind to anything that moves the whole estate at once, and the only "
                         "baseline that survives one. A broadcast storm on every port looks normal here."),
            series=[viz.Series("traffic_bps", "traffic", display_scale=1e6),
                    viz.Series("peer_center", "peer median", color=viz.PALETTE["peer"], display_scale=1e6)],
            band=viz.Band("peer_lo", "peer_hi", "peer +/-3 MAD", color=viz.PALETTE["peer"]),
            unit="megabytes_per_sec", height=8),
        viz.PanelSpec(
            title="Quality features: error and discard rate",
            description=("Near zero almost always. A z-score against a near-constant metric is "
                         "meaningless, which is why these want a fixed threshold on the raw count."),
            series=[viz.Series("error_rate", "error rate", color=viz.PALETTE["alert"]),
                    viz.Series("discard_rate", "discard rate", color=viz.PALETTE["baseline"])],
            unit="ratio", height=7),
        viz.PanelSpec(
            title="Shape features: mean packet size, broadcast and multicast share",
            description=("Traffic volume is blind to a scan made of tiny packets and to an L2 loop. "
                         "These are not."),
            series=[viz.Series("avg_pkt_bytes", "mean packet bytes", color=viz.PALETTE["signal"]),
                    viz.Series("broadcast_ratio", "broadcast share", color=viz.PALETTE["alert"]),
                    viz.Series("multicast_ratio", "multicast share", color=viz.PALETTE["peer"])],
            unit="none", height=7),
    ]
    panels += viz.layout(specs, uid, selector=selector, start_id=pid, start_y=4)

    return viz.dashboard(
        "Lab 01 - Features and baselines", "aiops-lab01", panels,
        tags=["aiops-workshop", "lab01"], time_from="now-30m", refresh="10s",
        variables=[viz.port_variable(uid)],
        description="Five baselines over the same traffic. Which one can see your fault?")


def lab02_dashboard(uid: str) -> dict:
    """Lab 02 separates score, label and alert, and scores the result."""
    selector = {"port_id": "$port"}
    panels: list[dict] = []
    pid = 1

    panels.append(viz.text_panel(
        "Score, label, alert", (
            "Three different things, and collapsing them is what produces alert storms.\n\n"
            "- **Score** is continuous: how far from baseline, in sigma.\n"
            "- **Label** is the binary judgement after a threshold.\n"
            "- **Alert** is what reaches a human, after duration, minimum volume, "
            "maintenance suppression, severity and deduplication.\n\n"
            "The scorecard is measured against known incidents. "
            "**Event recall** is the share of incidents caught at least once; "
            "**alerts/day** is what your on-call rota has to absorb. "
            "Moving a threshold trades one for the other, and there is no setting that wins both."
        ), pid, {"h": 5, "w": 24, "x": 0, "y": 0}))
    pid += 1

    tiles = [
        ("Event recall", "eval_event_recall", "ratio",
         "Share of known incidents caught at least once. The headline number."),
        ("Alerts per day", "eval_alerts_per_day", "count",
         "Notification burden. Compare against what your team can actually read."),
        ("Median detection delay", "eval_mttd_min", "minutes",
         "Minutes from incident start to first alert. Drives MTTD."),
        ("Unexplained false alerts", "eval_false_unexplained", "count",
         "False alerts not covered by a planned change. These are modelling failures."),
    ]
    for n, (title, column, unit, desc) in enumerate(tiles):
        panels.append(viz.stat_panel(
            title, column, uid, unit=unit, selector=None,
            grid={"h": 4, "w": 6, "x": 6 * n, "y": 5}, panel_id=pid,
            decimals=2, description=desc))
        pid += 1

    specs = [
        viz.PanelSpec(
            title="Layer 1 - anomaly score by detector",
            description=("Same traffic, four baselines, four scores. Where they disagree is where "
                         "the choice of baseline is doing the work."),
            series=[viz.Series("score_rolling", "rolling z", color=viz.PALETTE["muted"]),
                    viz.Series("score_robust", "robust z", color=viz.PALETTE["signal"]),
                    viz.Series("score_seasonal", "seasonal z", color=viz.PALETTE["baseline"]),
                    viz.Series("score_peer", "peer z", color=viz.PALETTE["peer"])],
            thresholds=[viz.ThresholdLine(4.0, "decision threshold")],
            unit="sigma", height=9),
        viz.PanelSpec(
            # CUSUM is normalised so that 1.0 is its decision limit, not 4.0.
            # Sharing an axis with the z-scores would put two different meanings
            # of "over the line" on one threshold, so it gets its own panel.
            title="Layer 1b - CUSUM, an accumulating statistic",
            description=("A z-score forgets each sample immediately. CUSUM adds up small "
                         "deviations, so a drift too gentle to ever look alarming still reaches "
                         "the limit. The limit here is 1.0, not 4.0, and the arm resets after "
                         "each crossing."),
            series=[viz.Series("score_cusum", "CUSUM score", color=viz.PALETTE["score"]),
                    viz.Series("score_robust", "robust z, for comparison",
                               color=viz.PALETTE["muted"], kind="dashed", width=0.8)],
            thresholds=[viz.ThresholdLine(1.0, "CUSUM decision limit")],
            unit="none", height=7),
        viz.PanelSpec(
            title="Layer 2 - label, and Layer 3 - alert after policy",
            description=("The gap between the two rows is everything the alert policy removed: "
                         "single-sample noise, low-volume ratios, planned maintenance."),
            series=[viz.Series("label", "label (score over threshold)", color=viz.PALETTE["muted"]),
                    viz.Series("alert", "alert (policy applied)", color=viz.PALETTE["alert"])],
            kind="state", unit="none", height=6),
        viz.PanelSpec(
            title="Evidence - traffic against the baseline that fired",
            description="What a responder needs to see first: the signal, its baseline, and the expected range.",
            series=[viz.Series("traffic_bps", "traffic", display_scale=1e6),
                    viz.Series("robust_center", "baseline", color=viz.PALETTE["baseline"], display_scale=1e6)],
            band=viz.Band("robust_lo", "robust_hi", "expected range"),
            markers="alert",
            unit="megabytes_per_sec", height=9),
        viz.PanelSpec(
            title="Ground truth - known incident windows",
            description=("1 during a labelled incident. Every gap where the alert row above is flat "
                         "and this row is high is a missed event."),
            series=[viz.Series("is_incident", "labelled incident", color=viz.PALETTE["truth"]),
                    viz.Series("is_planned", "planned change", color=viz.PALETTE["peer"])],
            kind="state", unit="none", height=5),
    ]
    panels += viz.layout(specs, uid, selector=selector, start_id=pid, start_y=9)

    return viz.dashboard(
        "Lab 02 - Detection, scores and alerts", "aiops-lab02", panels,
        tags=["aiops-workshop", "lab02"], time_from="now-30m", refresh="10s",
        variables=[viz.port_variable(uid)],
        description="Score to label to alert, scored against known incidents.")


# ---------------------------------------------------------------------------
# Alert rules
# ---------------------------------------------------------------------------

def evidence_panel_id(dashboard: dict) -> int:
    """Panel an alert should open onto, found by title rather than hardcoded.

    Grafana requires __dashboardUid__ and __panelId__ together; supplying them
    puts a working "View panel" link in every notification, which is half of
    what makes an alert actionable.
    """
    for panel in dashboard["panels"]:
        if panel.get("title", "").startswith("Evidence"):
            return int(panel["id"])
    return 1


def alert_rule(title: str, expr: str, threshold: float, for_duration: str,
               severity: str, summary: str, panel_id: int, group: str = "lab02",
               reducer: str = "last", comparator: str = "gt") -> dict:
    """A Grafana alert rule in the shape the provisioning API expects.

    Three stages, which is exactly the score/label/alert split: A queries the
    score, B reduces it to one number per series, C compares it to a threshold.
    `for` is the deadband, expressed as duration rather than sample count.
    """
    return {
        "title": title,
        "ruleGroup": group,
        "folderUID": FOLDER_UID,
        "condition": "C",
        "for": for_duration,
        "orgID": 1,
        "noDataState": "OK",
        "execErrState": "OK",
        "labels": {"severity": severity, "workshop": "aiops"},
        "annotations": {
            "summary": summary,
            "description": (
                "Port {{ $labels.port_id }} ({{ $labels.port_role }}) scored "
                "{{ $values.B }} against its baseline. Open the Lab 02 dashboard, "
                "check the evidence panel, then confirm against the change calendar "
                "before escalating."
            ),
            "__dashboardUid__": "aiops-lab02",
            "__panelId__": str(panel_id),
        },
        "data": [
            {"refId": "A", "relativeTimeRange": {"from": 900, "to": 0},
             "datasourceUid": "prometheus",
             "model": {"refId": "A", "expr": expr, "instant": False, "range": True,
                       "editorMode": "code"}},
            {"refId": "B", "datasourceUid": "__expr__",
             "model": {"refId": "B", "type": "reduce", "expression": "A",
                       "reducer": reducer, "settings": {"mode": "dropNN"}}},
            {"refId": "C", "datasourceUid": "__expr__",
             "model": {"refId": "C", "type": "threshold", "expression": "B",
                       "conditions": [{"evaluator": {"type": comparator, "params": [threshold]}}]}},
        ],
    }


def workshop_alert_rules(panel_id: int) -> list[dict]:
    """Three rules chosen to make three different points.

    The first is a statistical baseline on a well-behaved metric. The second is
    the same idea on a metric that only a shape feature can see. The third is
    deliberately *not* statistical, because its metric has no usable scale.
    """
    return [
        alert_rule(
            "Traffic deviation from robust baseline",
            'aiops_python_result{column="score_robust"}', 4.0, "10m", "warning",
            "Traffic on {{ $labels.port_id }} is far from its 1-hour robust baseline",
            panel_id,
        ),
        alert_rule(
            "Broadcast share elevated",
            'aiops_python_result{column="score_broadcast"}', 6.0, "5m", "critical",
            "Broadcast share on {{ $labels.port_id }} suggests an L2 loop or ARP storm",
            panel_id,
        ),
        alert_rule(
            # A fixed threshold on the raw count, deliberately. The error rate is
            # exactly zero for 99.8% of samples, so every scale estimate collapses
            # and a z-score against it is not a measurement. Rules beat statistics
            # when the metric has a hard, known-meaningful boundary.
            "Interface errors present",
            'aiops_python_result{column="errors_pps"}', 0.05, "10m", "critical",
            "Interface errors on {{ $labels.port_id }}: check cable, SFP, duplex",
            panel_id,
        ),
    ]


def maintenance_mute_timing() -> dict:
    """Suppression window covering the declared change calendar.

    An alert firing during declared maintenance is a suppression failure with a
    known fix, not a detection success. Omitting `weekdays` means every day:
    Grafana parses Sunday as day zero, so a "monday:sunday" range is rejected as
    backwards.
    """
    return {
        "name": MUTE_TIMING,
        "time_intervals": [{
            "times": [{"start_time": "00:30", "end_time": "05:00"}],
        }],
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def ensure_folder(client: GrafanaClient) -> bool:
    try:
        _request(f"{client.url}/api/folders/{FOLDER_UID}", auth=client._auth())
        return True
    except Exception:
        pass
    try:
        _request(f"{client.url}/api/folders", method="POST", auth=client._auth(),
                 payload={"uid": FOLDER_UID, "title": FOLDER_TITLE})
        return True
    except Exception as error:
        print(f"  folder: {error}")
        return False


def existing_rule_uids(client: GrafanaClient) -> dict:
    try:
        rules = _request(f"{client.url}/api/v1/provisioning/alert-rules", auth=client._auth())
    except Exception:
        return {}
    return {r["title"]: r["uid"] for r in rules if r.get("folderUID") == FOLDER_UID}


def push_alert_rules(client: GrafanaClient, rules: list[dict]) -> int:
    """Create or replace each rule, keeping it editable in the UI."""
    known = existing_rule_uids(client)
    pushed = 0
    for rule in rules:
        uid = known.get(rule["title"])
        try:
            if uid:
                _request(f"{client.url}/api/v1/provisioning/alert-rules/{uid}",
                         method="DELETE", auth=client._auth())
            _request(f"{client.url}/api/v1/provisioning/alert-rules", method="POST",
                     auth=client._auth(), payload=rule,
                     headers={"X-Disable-Provenance": "true"})
            pushed += 1
        except Exception as error:
            print(f"  alert rule '{rule['title']}': {error}")
    return pushed


def push_mute_timing(client: GrafanaClient, timing: dict) -> bool:
    try:
        _request(f"{client.url}/api/v1/provisioning/mute-timings/{timing['name']}",
                 method="DELETE", auth=client._auth())
    except Exception:
        pass
    try:
        _request(f"{client.url}/api/v1/provisioning/mute-timings", method="POST",
                 auth=client._auth(), payload=timing,
                 headers={"X-Disable-Provenance": "true"})
        return True
    except Exception as error:
        print(f"  mute timing: {error}")
        return False


def reset(client: GrafanaClient) -> None:
    for uid in existing_rule_uids(client).values():
        try:
            _request(f"{client.url}/api/v1/provisioning/alert-rules/{uid}",
                     method="DELETE", auth=client._auth())
        except Exception:
            pass
    try:
        _request(f"{client.url}/api/v1/provisioning/mute-timings/{MUTE_TIMING}",
                 method="DELETE", auth=client._auth())
    except Exception:
        pass
    for uid in ("aiops-lab00", "aiops-lab01", "aiops-lab02"):
        try:
            _request(f"{client.url}/api/dashboards/uid/{uid}", method="DELETE", auth=client._auth())
        except Exception:
            pass
    print("removed existing workshop objects")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths.ensure_dirs()
    client = GrafanaClient(url=args.url, user=args.user, password=args.password)

    if args.dry_run:
        for builder in (lab00_dashboard, lab01_dashboard, lab02_dashboard):
            dash = builder("prometheus")
            path = paths.GRAFANA_DASHBOARD_DIR / f"{dash['uid']}.json"
            path.write_text(json.dumps(dash, indent=2))
            print(f"wrote {path.relative_to(paths.ROOT)}  ({len(dash['panels'])} panels)")
        return 0

    if not client.healthy():
        print(f"Grafana is not reachable at {args.url}.")
        print("  macOS  brew services start grafana")
        print("  Linux  sudo systemctl start grafana-server")
        print("Then run this script again. Use --dry-run to write the JSON without Grafana.")
        return 1

    if args.reset:
        reset(client)

    datasource_uid = client.prometheus_uid()
    print(f"datasource     {datasource_uid or 'FAILED'}")
    if not datasource_uid:
        print("  could not find or create a Prometheus datasource; is Prometheus running on :9090?")
        return 1

    print(f"folder         {FOLDER_TITLE if ensure_folder(client) else 'FAILED'}")

    panel_id = 1
    for builder in (lab00_dashboard, lab01_dashboard, lab02_dashboard):
        dash = builder(datasource_uid)
        if dash["uid"] == "aiops-lab02":
            panel_id = evidence_panel_id(dash)
        path = paths.GRAFANA_DASHBOARD_DIR / f"{dash['uid']}.json"
        path.write_text(json.dumps(dash, indent=2))
        url = client.upload(dash, folder_uid=FOLDER_UID)
        print(f"dashboard      {dash['title']:<42} {url or 'upload failed'}")

    print(f"alert rules    {push_alert_rules(client, workshop_alert_rules(panel_id))} of 3 created")
    print(f"mute timing    {'created' if push_mute_timing(client, maintenance_mute_timing()) else 'FAILED'}")

    print()
    print("Open these, in order:")
    print(f"  {args.url}/d/aiops-lab00   pipeline check")
    print(f"  {args.url}/d/aiops-lab01   features and baselines")
    print(f"  {args.url}/d/aiops-lab02   detection, scores and alerts")
    print(f"  {args.url}/alerting/list   the three alert rules, editable")
    print()
    print("The dashboards are empty until a notebook publishes results and the exporter runs:")
    print("  REPLAY_SPEED_X=720 python infra/python_results_exporter.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
