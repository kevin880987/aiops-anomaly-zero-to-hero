"""Attribution, root-cause measures, and the evidence packet Lab 08 hands to a language model.

Everything before this file answers "is something wrong". Nothing before this file answers "what
is wrong, where, and is it ours to fix". Labs 03 and 04 score detection and delay, Lab 05 scores
notification policy, and no lab so far scores a root cause at all, which leaves the one claim an
operator actually acts on as the only unmeasured claim in the course.

Four measures, and each fails independently of the others:

    attribution     did the explanation name the counter that moved
    localization    did it name the right ports, and only those
    cause typing    did it name the right kind of incident
    suppression     did it stay quiet for the changes that were announced

A method can win one and lose another. Peer context moves localization and leaves attribution
untouched; the change calendar moves suppression and costs recall. Reporting one number for
"RCA quality" would hide exactly those trades, so the four stay apart.
"""
import json

import numpy as np
import pandas as pd

from .features import FAULT_SIGNATURE, FEATURES

def random_baseline(features=FEATURES, k=1):
    """hit@k a uniformly random pick would score, so a table of hit rates has a floor to beat.

    Computed rather than written down. A signature table that gains an incident type moves this
    number, and a hardcoded one would go quietly wrong at exactly that moment.
    """
    n = len(features)
    rates = []
    for signature in FAULT_SIGNATURE.values():
        present = len([f for f in signature if f in features])
        miss = 1.0
        for i in range(k):                      # probability every one of k draws misses
            miss *= max(n - present - i, 0) / max(n - i, 1)
        rates.append(1 - miss)
    return round(float(np.mean(rates)), 3)


# --------------------------------------------------------------------------- attribution
def normalise(shares):
    total = float(np.sum(shares))
    return np.asarray(shares, float) / total if total > 0 else np.full(len(shares), np.nan)


def attribution_absz(z_row, features=FEATURES):
    """R0. Share of the deviation each feature carries, in robust units.

    The naive answer, and the one every operator reaches for first. Its weakness is structural
    rather than statistical: a ratio whose denominator moved reads as a large deviation even
    though nothing in its numerator changed.
    """
    return pd.Series(normalise(np.abs(z_row)), index=features)


def attribution_spe(spe_row, features=FEATURES):
    """R1. Share of the PCA reconstruction error each feature contributes.

    Free, because an additive score decomposes itself. Squared error is the catch: a feature
    whose residual distribution is heavy-tailed dominates the sum even when the incident had
    nothing to do with it.
    """
    return pd.Series(normalise(spe_row), index=features)


def attribution_leave_one_out(model, z_row, detector, features=FEATURES):
    """R2. Drop in the score when one feature is returned to its seasonal normal.

    A perturbation measure rather than a decomposition, so it works for any detector including
    the ones with no additive structure at all. It is the honest reading of "how much of this
    score does this feature account for", and it costs one rescore per feature.

    Correlated features share the blame here rather than splitting it: zero one of a correlated
    pair and the other still carries the signal, so both look unimportant. R3 is the answer to
    that.
    """
    base = _score_one(model, z_row, detector)
    drops = []
    for j in range(len(features)):
        perturbed = np.array(z_row, float)
        perturbed[j] = 0.0
        drops.append(max(base - _score_one(model, perturbed, detector), 0.0))
    return pd.Series(normalise(drops), index=features)


def attribution_counterfactual(model, z_row, detector, features=FEATURES):
    """R3. Score kept by each feature alone, with every other feature held at normal.

    The mirror image of leave-one-out, and the one that survives correlation. Instead of asking
    what the score loses without a feature, it asks what the score would still be if that feature
    were the only thing out of place. Two counters that moved together both keep a large score on
    their own, so neither disappears the way it does under R2.
    """
    kept = []
    for j in range(len(features)):
        alone = np.zeros(len(features))
        alone[j] = z_row[j]
        kept.append(max(_score_one(model, alone, detector), 0.0))
    return pd.Series(normalise(kept), index=features)


def _score_one(model, z_row, detector):
    """One detector's score for a single already-standardised row."""
    z = np.asarray(z_row, float).reshape(1, -1)
    if detector == "Max |z|":
        return float(np.abs(z).max())
    if detector == "Mahalanobis":
        return float(np.sqrt(max(model.lw_.mahalanobis(z)[0], 0.0)))
    if detector == "Robust Mahalanobis":
        return float(np.sqrt(max(model.mcd_.mahalanobis(z)[0], 0.0)))
    projected, reconstruction, centred, eigenvalues = model._pca_parts(z)
    if detector == "PCA T2":
        return float((projected ** 2 / eigenvalues).sum())
    if detector == "PCA SPE":
        return float(((centred - reconstruction) ** 2).sum())
    if detector == "LOF":
        return float(-model.lof_.score_samples(z)[0])
    if detector == "IsolationForest":
        return float(-model.iforest_.score_samples(z)[0])
    raise ValueError(f"unknown detector: {detector}")


ATTRIBUTIONS = ("R0 max |z|", "R1 PCA SPE share", "R2 leave-one-out", "R3 counterfactual")


def attribute_window(model, frame, rows, peak_row, detector, features=FEATURES):
    """Every attribution method for one incident window, evaluated at its worst sample."""
    local = frame.loc[rows].reset_index(drop=True)
    position = list(rows).index(peak_row)
    z = model.standardize(local)[position]
    spe = model.per_feature_spe(local)[position]
    return {
        "R0 max |z|": attribution_absz(z, features),
        "R1 PCA SPE share": attribution_spe(spe, features),
        "R2 leave-one-out": attribution_leave_one_out(model, z, detector, features),
        "R3 counterfactual": attribution_counterfactual(model, z, detector, features),
    }


# --------------------------------------------------------------------------- measure 1
def attribution_hits(attributions, event_type, k=1):
    """Did the top-k features include one this incident type is supposed to move?"""
    signature = FAULT_SIGNATURE[event_type]
    top = list(attributions.sort_values(ascending=False).index[:k])
    return bool(set(top) & signature)


def attribution_table(models, frame, scores, windows, detector, ks=(1, 3)):
    """hit@k for every attribution method over every incident window. One row per window."""
    rows = []
    for window in windows.itertuples():
        mask = ((frame["port_id"] == window.port_id)
                & frame["timestamp"].between(window.start, window.end))
        idx = frame.index[mask]
        peak = scores.loc[idx, detector].idxmax()
        found = attribute_window(models[window.port_id], frame, idx, peak, detector)
        row = {"event_id": window.event_id, "event_type": window.event_type,
               "port": window.port_id[-4:]}
        for name, shares in found.items():
            row[f"{name} top1"] = shares.sort_values(ascending=False).index[0]
            for k in ks:
                row[f"{name} hit@{k}"] = attribution_hits(shares, window.event_type, k)
        rows.append(row)
    return pd.DataFrame(rows)


def attribution_summary(table, ks=(1, 3)):
    """hit@k per attribution method, collapsed over windows."""
    rows = []
    for name in ATTRIBUTIONS:
        row = {"attribution": name}
        for k in ks:
            row[f"hit@{k}"] = round(float(table[f"{name} hit@{k}"].mean()), 3)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("hit@1", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- measure 2
def localization(frame, flags, windows, catalog):
    """Which ports an incident was reported on, against which ports it actually touched.

    Two failure directions and they cost different things. Missing a port understates the blast
    radius, so the switch-wide event reads as one port misbehaving. Adding a port sends an
    engineer to hardware that is fine. Reporting only one of the two would hide whichever the
    method is worse at.
    """
    flags = np.asarray(flags, bool)
    all_ports = set(frame["port_id"].unique())
    rows = []
    for event_id, group in windows.groupby("event_id"):
        truth = set(group["port_id"])
        start, end = group["start"].min(), group["end"].max()
        window = frame["timestamp"].between(start, end).to_numpy()
        fired = set(frame.loc[window & flags, "port_id"].unique())
        scope = catalog.loc[catalog["event_id"] == event_id, "port_id"].iloc[0]
        rows.append({
            "event_id": event_id,
            "event_type": group["event_type"].iloc[0],
            "catalog_scope": scope,
            "ports_true": len(truth),
            "ports_fired": len(fired),
            "missed": len(truth - fired),
            "spurious": len(fired - truth),
            "jaccard": round(len(truth & fired) / max(len(truth | fired), 1), 3),
            "common_mode_called": len(fired) >= 0.6 * len(all_ports),
            "common_mode_true": len(truth) >= 0.6 * len(all_ports),
        })
    out = pd.DataFrame(rows)
    out.attrs["mean_jaccard"] = round(float(out["jaccard"].mean()), 3)
    out.attrs["common_mode_accuracy"] = round(
        float((out["common_mode_called"] == out["common_mode_true"]).mean()), 3)
    return out


# --------------------------------------------------------------------------- measure 3
def predict_event_type(attributions, floor=0.05):
    """Name the incident type whose signature best matches the attributed shares.

    Two things have to hold before a type is a good fit, and scoring only one of them fails in a
    different direction each time. Coverage is how much of the explanation lands on that type's
    signature. Specificity is how much of the signature was actually moved, which is what stops a
    type whose signature contains another's from winning every time by inclusion:
    load_sensitive_link_issue carries error_rate as well as the two volume counters, so on a pure
    link fault it has full coverage and one third specificity while link_quality_issue has both.

    Set membership over a top-k list cannot see either. It ties every pair of single-counter
    signatures against each other, and the tie then falls to whatever the sort order happens to
    be, which is how a broadcast storm gets reported as multicast flooding.

    A lookup against the engineering table rather than a trained classifier. Ten labelled
    incidents is nothing to train on, and a rule an engineer can disagree with is worth more here
    than a model nobody can inspect.
    """
    shares = attributions.fillna(0.0)
    scored = []
    for name, signature in sorted(FAULT_SIGNATURE.items()):
        present = [f for f in signature if f in shares.index]
        if not present:
            continue
        coverage = float(shares[present].sum())
        specificity = float(np.mean([shares[f] >= floor for f in present]))
        scored.append((coverage * specificity, name))
    best = max(scored) if scored else (0.0, "unclassified")
    return best[1] if best[0] > 0 else "unclassified"


def cause_typing(models, frame, scores, windows, detector, method="R3 counterfactual"):
    """Predicted incident type against the labelled one, per window."""
    rows = []
    for window in windows.itertuples():
        mask = ((frame["port_id"] == window.port_id)
                & frame["timestamp"].between(window.start, window.end))
        idx = frame.index[mask]
        peak = scores.loc[idx, detector].idxmax()
        shares = attribute_window(models[window.port_id], frame, idx, peak, detector)[method]
        predicted = predict_event_type(shares)
        rows.append({"event_id": window.event_id, "port": window.port_id[-4:],
                     "true_type": window.event_type, "predicted_type": predicted,
                     "correct": predicted == window.event_type})
    return pd.DataFrame(rows)


def confusion(typing):
    return pd.crosstab(typing["true_type"], typing["predicted_type"])


# --------------------------------------------------------------------------- measure 4
def suppression(frame, flags, windows, planned_mask, catalog, calendar):
    """What the change calendar silences, and what that costs.

    An announced change and a real fault look identical on the wire, which is the whole reason
    the calendar exists. The number that matters is not how much noise it removes but whether it
    ever removes a real fault, because that failure is silent and arrives as an outage nobody was
    paged for.
    """
    flags = np.asarray(flags, bool)
    planned_mask = np.asarray(planned_mask, bool)
    announced = set(catalog.loc[catalog["event_id"].isin(_announced_events(
        frame, windows, planned_mask)), "event_id"])

    kept = flags & ~planned_mask
    rows = []
    for name, active in (("no calendar", flags), ("calendar applied", kept)):
        outcomes = []
        for window in windows.itertuples():
            mask = ((frame["port_id"] == window.port_id)
                    & frame["timestamp"].between(window.start, window.end)).to_numpy()
            outcomes.append({"event_id": window.event_id,
                             "announced": window.event_id in announced,
                             "detected": bool((active & mask).any())})
        outcomes = pd.DataFrame(outcomes)
        real = outcomes[~outcomes["announced"]]
        rows.append({
            "arm": name,
            "real_faults_caught": f"{int(real['detected'].sum())}/{len(real)}",
            "announced_still_alerting": int(outcomes.loc[outcomes["announced"], "detected"].sum()),
            "announced_windows": int(outcomes["announced"].sum()),
            "alert_samples": int(active.sum()),
        })
    out = pd.DataFrame(rows)
    out.attrs["announced_events"] = sorted(announced)
    return out


def _announced_events(frame, windows, planned_mask):
    """Incidents at least half of whose samples sit inside an announced change window."""
    planned_mask = np.asarray(planned_mask, bool)
    announced = []
    for window in windows.itertuples():
        mask = ((frame["port_id"] == window.port_id)
                & frame["timestamp"].between(window.start, window.end)).to_numpy()
        if mask.sum() and (planned_mask & mask).sum() / mask.sum() >= 0.5:
            announced.append(window.event_id)
    return sorted(set(announced))


# --------------------------------------------------------------------------- evidence packet
def peer_context(frame, scores, thresholds, detector, start, end, subject_port):
    """Which other ports were also out of band over the same window.

    The single signal that separates a port fault from something upstream of every port. The
    subject is excluded from its own peer group, because including it would report at least one
    deviating port for every incident that ever happened.
    """
    window = frame["timestamp"].between(start, end).to_numpy()
    peers = []
    for port, group in frame.groupby("port_id", sort=True):
        if port == subject_port:
            continue
        rows = group.index[window[group.index]]
        if not len(rows):
            continue
        peak = float(scores.loc[rows, detector].max())
        limit = thresholds[(detector, port)]
        peers.append({"port_id": port, "peak_over_threshold": round(peak / limit, 2)
                      if limit > 0 else np.nan, "deviating": bool(peak > limit)})
    return {"peers": peers, "n_deviating": sum(p["deviating"] for p in peers),
            "n_peers": len(peers)}


def build_incident_context(frame, scores, thresholds, models, windows, catalog, calendar,
                           planned_mask, event_id, port_id, detector,
                           method="R3 counterfactual"):
    """One incident compressed into the structured packet a language model is allowed to read.

    Everything here was computed by a tool. The model's job downstream is to render and rank
    what the packet already contains, never to derive a cause from raw telemetry it cannot see.
    """
    window = windows[(windows["event_id"] == event_id)
                     & (windows["port_id"] == port_id)].iloc[0]
    mask = ((frame["port_id"] == port_id)
            & frame["timestamp"].between(window.start, window.end))
    idx = frame.index[mask]
    peak = scores.loc[idx, detector].idxmax()
    model = models[port_id]
    shares = attribute_window(model, frame, idx, peak, detector)[method]
    ranked = shares.sort_values(ascending=False)
    row = frame.loc[peak]

    reference = frame.loc[(frame["port_id"] == port_id)
                          & (frame["timestamp"] < window.start)].tail(288)
    peers = peer_context(frame, scores, thresholds, detector, window.start, window.end, port_id)
    change = calendar[(calendar["start_time"] <= row["timestamp"])
                      & (calendar["end_time"] >= row["timestamp"])
                      & ((calendar["scope"] == port_id)
                         | (calendar["scope"] == row["device_id"]))]

    return {
        "device_id": str(row["device_id"]),
        "port_id": str(port_id),
        "port_role": str(row["port_role"]),
        "window_start": str(window.start),
        "duration_min": int((window.end - window.start).total_seconds() / 60) + 5,
        "detector": detector,
        "score": round(float(scores.loc[peak, detector]), 1),
        "threshold": round(float(thresholds[(detector, port_id)]), 1),
        "score_over_threshold": round(float(scores.loc[peak, detector])
                                      / max(float(thresholds[(detector, port_id)]), 1e-9), 1),
        "attribution_method": method,
        "attribution_top3": {k: round(float(v), 3) for k, v in ranked.head(3).items()},
        "measured_at_peak": {f: round(float(row[f]), 4) for f in ranked.head(3).index},
        "normal_median": {f: round(float(reference[f].median()), 4) for f in ranked.head(3).index},
        "peer_ports_deviating": peers["n_deviating"],
        "peer_ports_total": peers["n_peers"],
        "planned_change": (str(change["change_id"].iloc[0]) if len(change) else ""),
        "planned_change_description": (str(change["description"].iloc[0]) if len(change) else ""),
        "candidate_type_from_signature": predict_event_type(shares),
        "ground_truth_type": str(window.event_type),
    }


# --------------------------------------------------------------------------- tools and agent
TOOLS = [
    {"name": "get_recent_metrics",
     "description": "Recent measured values for one port over a stated window."},
    {"name": "check_related_devices",
     "description": "Whether other ports deviated over the same window."},
    {"name": "check_change_calendar",
     "description": "Whether an announced change covers this port and time."},
    {"name": "create_incident_summary",
     "description": "Record a ranked cause list and the actions proposed. Requires human sign-off."},
]

AGENT_SYSTEM_PROMPT = (
    "You are a network incident investigator. Evidence is supplied by monitoring tools. "
    "Use only the values in the packet and the tool results. Never invent a number. "
    "Cite the packet field behind every claim. Rank causes, give the runner-up, and state what "
    "further evidence would separate them. If the packet cannot distinguish a real fault from an "
    "announced change, say so. No action executes without human approval."
)


def grounded_prompt(packet):
    """The packet plus the rules that make its output checkable."""
    return (AGENT_SYSTEM_PROMPT + "\n\nRules:\n"
            "1. Use only the numbers in the packet.\n"
            "2. Every claim cites its field, for example [attribution_top3].\n"
            "3. One most-supported cause, one runner-up, the evidence for each.\n"
            "4. Say which further measurement would separate them.\n"
            "5. Give confidence as low, medium or high, and answer in at most five sentences.\n\n"
            "EVIDENCE PACKET:\n" + json.dumps(_redacted(packet), ensure_ascii=False, indent=2))


def loose_prompt(packet):
    """The arm with no rules, kept so the comparison in section 12 has something to compare to."""
    return ("You are a network expert. Explain the root cause of this incident:\n"
            + json.dumps(_redacted(packet), ensure_ascii=False, indent=2))


def _redacted(packet):
    """The packet as a model may see it. The answer key never crosses this boundary."""
    return {k: v for k, v in packet.items() if k != "ground_truth_type"}


def make_tools(frame, scores, thresholds, calendar, detector):
    """Bind the tool implementations to this notebook's data. The adapter boundary.

    Pointing these four functions at a live Prometheus is the whole of what production migration
    means here. Nothing above this line knows where the numbers came from.
    """
    recorded = []

    def get_recent_metrics(port_id, until, minutes=60):
        until = pd.Timestamp(until)
        rows = frame[(frame["port_id"] == port_id)
                     & (frame["timestamp"] > until - pd.Timedelta(minutes=minutes))
                     & (frame["timestamp"] <= until)]
        if rows.empty:
            return {"port_id": port_id, "samples": 0, "note": "no samples in window"}
        return {"port_id": port_id, "samples": int(len(rows)), "window_min": minutes,
                **{f: round(float(rows[f].max()), 4) for f in
                   ("in_bps", "out_bps", "error_rate", "discard_rate", "broadcast_ratio",
                    "multicast_ratio", "unknown_proto_pps")}}

    def check_related_devices(start, end, exclude_port_id):
        return peer_context(frame, scores, thresholds, detector,
                            pd.Timestamp(start), pd.Timestamp(end), exclude_port_id)

    def check_change_calendar(port_id, at):
        at = pd.Timestamp(at)
        device = frame.loc[frame["port_id"] == port_id, "device_id"].iloc[0]
        hit = calendar[(calendar["start_time"] <= at) & (calendar["end_time"] >= at)
                       & ((calendar["scope"] == port_id) | (calendar["scope"] == device))]
        if hit.empty:
            return {"announced": False}
        return {"announced": True, "change_id": str(hit["change_id"].iloc[0]),
                "change_type": str(hit["change_type"].iloc[0]),
                "description": str(hit["description"].iloc[0])}

    def create_incident_summary(severity, root_causes, actions, escalate=False):
        record = {"severity": severity, "root_causes": list(root_causes),
                  "actions": list(actions), "escalate": bool(escalate),
                  "approved_by_human": False}
        recorded.append(record)
        return {"recorded": True, "pending_human_approval": True}

    handlers = {"get_recent_metrics": get_recent_metrics,
                "check_related_devices": check_related_devices,
                "check_change_calendar": check_change_calendar,
                "create_incident_summary": create_incident_summary}

    def call_tool(name, payload):
        if name not in {t["name"] for t in TOOLS}:
            raise ValueError(f"{name} is not a declared tool: {[t['name'] for t in TOOLS]}")
        return handlers[name](**payload)

    return call_tool, recorded


def run_rca_agent(packet, call_tool):
    """A deterministic stand-in for a model, keeping the tool loop and dropping the sampling.

    The course runs with no API key and has to produce the same output on every machine, so the
    reasoning here is a decision table rather than a model. What it preserves is the part worth
    teaching: the tool set is declared up front, the agent may call nothing outside it, evidence
    arrives through those calls, and the summary it writes is marked as awaiting a human.
    """
    calls = []

    def invoke(name, payload):
        result = call_tool(name, payload)
        calls.append({"tool": name, "input": payload, "output": result})
        return result

    end = (pd.Timestamp(packet["window_start"])
           + pd.Timedelta(minutes=packet["duration_min"]))
    invoke("get_recent_metrics", {"port_id": packet["port_id"],
                                  "until": packet["window_start"], "minutes": 60})
    peers = invoke("check_related_devices", {"start": packet["window_start"],
                                             "end": str(end),
                                             "exclude_port_id": packet["port_id"]})
    change = invoke("check_change_calendar", {"port_id": packet["port_id"],
                                              "at": packet["window_start"]})

    top = list(packet["attribution_top3"])[0]
    if change["announced"]:
        cause = (f"announced change {change['change_id']} ({change['change_type']}), "
                 f"deviation on [{top}] is expected")
        confidence, severity, escalate = "high", "info", False
    elif peers["n_deviating"] >= 0.6 * peers["n_peers"]:
        cause = (f"common-mode event upstream of every port, "
                 f"{peers['n_deviating']} of {peers['n_peers']} peers deviating, "
                 f"leading counter [{top}]")
        confidence, severity, escalate = "high", "critical", True
    else:
        cause = (f"single-port fault on {packet['port_id']}, "
                 f"leading counter [{top}], no peer deviating")
        confidence, severity = "medium", "warning"
        escalate = packet["score_over_threshold"] >= 10

    runner_up = ("a load-driven side effect of an unannounced change"
                 if not change["announced"] else "a genuine fault coinciding with the change")
    report = (
        f"Cause: {cause}. Confidence {confidence}, from [attribution_top3] and "
        f"[peer_ports_deviating].\n"
        f"Runner-up: {runner_up}, not separated by [planned_change].\n"
        f"Evidence: score {packet['score']} against threshold {packet['threshold']}, "
        f"{packet['score_over_threshold']}x, from [score] and [threshold]. "
        f"Signature match suggests {packet['candidate_type_from_signature']}, "
        f"from [candidate_type_from_signature].\n"
        f"To separate them: confirm whether [{top}] moved on the peer ports at the same minute, "
        f"and whether a change ticket exists that was never filed.\n"
        f"Severity {severity}; escalation {'requested' if escalate else 'not requested'}, "
        f"pending human approval.")

    invoke("create_incident_summary",
           {"severity": severity, "root_causes": [cause, runner_up],
            "actions": ["confirm peer behaviour at the same minute",
                        "check for an unfiled change ticket"],
            "escalate": escalate})
    return report, calls


def score_rca_report(report, packet, predicted_type=None):
    """Two numbers a written root cause can be held to.

    Citation rate is how much of the text points at a field a reader can go and check. Type
    correctness compares the named incident kind against the label, which the model never saw.
    Neither measures whether the prose reads well, and that is deliberate: fluency is the thing
    an unusable report is most likely to have.
    """
    fields = set(packet) - {"ground_truth_type"}
    cited = {f for f in fields if f"[{f}]" in report}
    sentences = [s for s in report.replace("\n", " ").split(". ") if s.strip()]
    with_citation = sum(1 for s in sentences if "[" in s)
    predicted = predicted_type or packet["candidate_type_from_signature"]
    return {"sentences": len(sentences),
            "sentences_citing_a_field": with_citation,
            "citation_rate": round(with_citation / max(len(sentences), 1), 2),
            "distinct_fields_cited": len(cited),
            "predicted_type": predicted,
            "true_type": packet["ground_truth_type"],
            "type_correct": predicted == packet["ground_truth_type"]}
