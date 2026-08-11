"""Loading and feature engineering for the fleet-month telemetry that Lab 08 reads.

Lab 01 and Lab 02 read the same three files by hand, one cell at a time, because reading them
is part of what those labs teach. Lab 08 arrives after that lesson and needs the frame, not the
lesson, so the loading lives here and the notebook spends its cells on root-cause analysis.

Three files, and each answers a different question:

    synthetic_rrd_metrics.csv     what the ports did, per 5-minute interval
    synthetic_event_catalog.csv   which of those intervals were an incident, and of what kind
    change_calendar.csv           which of those intervals were announced in advance

The third file is what separates a fault from a change. Without it every scheduled backup is an
incident, and no detector can tell the difference, because on the wire there is none.
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

CADENCE_S = 300.0
SAMPLES_PER_DAY = int(round(86400 / CADENCE_S))

# The SNMP-style columns as the export writes them. Read as per-interval totals rather than as
# cumulative counters; load_telemetry() measures which of the two this file actually is and
# records the answer on the Contract instead of assuming it.
RAW_COLUMNS = ["INOCTETS", "OUTOCTETS", "INERRORS", "OUTERRORS",
               "INUCASTPKTS", "OUTUCASTPKTS", "INNUCASTPKTS", "OUTNUCASTPKTS",
               "INDISCARDS", "OUTDISCARDS", "INUNKNOWNPROTOS",
               "INBROADCASTPKTS", "OUTBROADCASTPKTS",
               "INMULTICASTPKTS", "OUTMULTICASTPKTS"]

# Lab 04's seven features, plus the four the fleet export supports and the scenario CSVs did not
# carry. The four additions are the whole reason Lab 08 reads this file: events D, E, F and J
# have no signature at all in Lab 04's vocabulary, so a capstone restricted to those seven
# features could not attribute four of the ten incident types even in principle.
FEATURES = ["in_bps", "out_bps", "in_pps", "out_pps", "avg_pkt_bytes",
            "broadcast_ratio", "multicast_ratio",
            "error_rate", "discard_rate", "unknown_proto_pps", "tx_ratio"]

LAB04_FEATURES = FEATURES[:7]

# What an engineer expects to move when this incident type happens, written from the incident
# descriptions rather than fitted to the data. That direction matters: an attribution measured
# against a table derived from the same data would score its own assumptions. Section 2 of the
# notebook prints the disagreement between this table and what the recorded counters did, and a
# disagreement is a finding about one of the two, never a licence to edit this table afterwards.
FAULT_SIGNATURE = {
    "business_traffic_growth":   {"in_bps", "out_bps", "in_pps", "out_pps"},
    "small_packet_scan":         {"avg_pkt_bytes", "in_pps", "out_pps"},
    "large_file_backup":         {"avg_pkt_bytes", "in_bps", "out_bps"},
    "queue_congestion":          {"discard_rate", "in_bps", "out_bps"},
    "link_quality_issue":        {"error_rate"},
    "load_sensitive_link_issue": {"error_rate", "in_bps", "out_bps"},
    "broadcast_storm":           {"broadcast_ratio"},
    "multicast_flooding":        {"multicast_ratio"},
    "abnormal_device_sender":    {"tx_ratio", "out_bps", "out_pps"},
    "unknown_protocol_scan":     {"unknown_proto_pps"},
}

# An incident type is announced when a row of the change calendar covers it. Membership is not a
# property of the waveform, it is a property of whether somebody filed the change, which is why
# this set is derived from the calendar at load time rather than hardcoded here.
PLANNED_CHANGE_TYPES = {"scheduled_backup", "business_change", "maintenance"}


def find_repo_root(start=None):
    """Walk upward until the folder holding data/synthetic appears.

    Same idiom Lab 04 and Lab 05 open with, so a notebook runs from its own directory or from
    the repository root without either one being the blessed one.
    """
    start = Path.cwd() if start is None else Path(start)
    for candidate in (start, *start.parents):
        if (candidate / "data" / "synthetic" / "synthetic_rrd_metrics.csv").exists():
            return candidate
    raise FileNotFoundError(
        "cannot locate the repository root: no ancestor of "
        f"{start} contains data/synthetic/synthetic_rrd_metrics.csv")


@dataclass
class Contract:
    """What the loader measured about the raw file, so the notebook can print it and argue.

    A data contract is a claim that has been checked, not a description that was written down.
    Every field here is measured from the file that was actually read.
    """
    n_rows: int
    n_ports: int
    span: tuple
    cadence_s: float
    semantics: str
    monotonic_fraction: float
    missing_cells: int
    duplicate_rows: int
    notes: list = field(default_factory=list)

    def describe(self):
        lo, hi = self.span
        lines = [
            f"rows            {self.n_rows:,} across {self.n_ports} ports",
            f"span            {lo}  ->  {hi}",
            f"cadence         {self.cadence_s:.0f} s "
            f"({self.cadence_s / 60:.0f} min, {int(round(86400 / self.cadence_s))} samples/day)",
            f"column reading  {self.semantics}",
            f"monotonic frac  {self.monotonic_fraction:.3f} of consecutive INOCTETS steps are "
            f"non-negative",
            f"missing cells   {self.missing_cells:,}",
            f"duplicate rows  {self.duplicate_rows:,}",
        ]
        return "\n".join(lines + [f"note            {n}" for n in self.notes])


def infer_cadence(timestamps, group):
    """Median positive sampling interval in seconds, measured within each series."""
    frame = pd.DataFrame({"ts": pd.to_datetime(timestamps), "g": np.asarray(group)})
    deltas = frame.sort_values(["g", "ts"]).groupby("g")["ts"].diff().dt.total_seconds()
    deltas = deltas[deltas > 0].dropna()
    if deltas.empty:
        raise ValueError("cannot infer cadence: no positive timestamp differences")
    return float(deltas.median())


def load_telemetry(root=None):
    """The month of port telemetry, plus the contract the loader was able to verify.

    Returns (frame, contract). The frame is sorted by port then time and its index is reset, so
    a numpy array of the same length lines up with it.
    """
    root = find_repo_root() if root is None else Path(root)
    path = root / "data" / "synthetic" / "synthetic_rrd_metrics.csv"
    raw = pd.read_csv(path, parse_dates=["timestamp"])

    missing = {c for c in ["timestamp", "port_id", "port_role", "device_id",
                           "event_label", "event_id", *RAW_COLUMNS]} - set(raw.columns)
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {sorted(missing)}")

    frame = raw.sort_values(["port_id", "timestamp"]).reset_index(drop=True)
    cadence = infer_cadence(frame["timestamp"], frame["port_id"])

    # A cumulative counter only ever goes up, apart from the wrap. Roughly half the steps here go
    # down, which settles the question: these columns are what happened during the interval, so
    # differencing them a second time would be measuring the wrong thing.
    steps = frame.groupby("port_id")["INOCTETS"].diff().dropna()
    monotonic = float((steps >= 0).mean())
    counterish = monotonic > 0.98
    semantics = ("cumulative counter, differencing required" if counterish else
                 "per-interval totals, already differenced")

    notes = []
    if not counterish:
        notes.append("rates come from dividing by the cadence, not from a diff")
    if (frame["INNUCASTPKTS"]
            < frame["INBROADCASTPKTS"] + frame["INMULTICASTPKTS"]).any():
        notes.append("INNUCASTPKTS is smaller than broadcast+multicast on some rows")
    labelled = frame["event_label"].ne("normal").sum()
    notes.append(f"{labelled:,} rows carry an incident label "
                 f"({labelled / len(frame):.3%} prevalence)")

    contract = Contract(
        n_rows=len(frame),
        n_ports=int(frame["port_id"].nunique()),
        span=(frame["timestamp"].min(), frame["timestamp"].max()),
        cadence_s=cadence,
        semantics=semantics,
        monotonic_fraction=monotonic,
        missing_cells=int(frame[RAW_COLUMNS].isna().sum().sum()),
        duplicate_rows=int(frame.duplicated(["port_id", "timestamp"]).sum()),
        notes=notes,
    )
    return frame, contract


def load_catalog(root=None):
    """The incident catalog, one row per labelled incident, with its engineering description."""
    root = find_repo_root() if root is None else Path(root)
    return pd.read_csv(root / "data" / "synthetic" / "synthetic_event_catalog.csv",
                       parse_dates=["start_time", "end_time"])


def load_calendar(root=None):
    """The change calendar: what operations announced in advance, and over which scope.

    `scope` is a port_id on some rows and a device_id on others, which is how a change is
    actually filed. calendar_mask() resolves that against the telemetry rather than making the
    caller guess which kind of name they are holding.
    """
    root = find_repo_root() if root is None else Path(root)
    return pd.read_csv(root / "data" / "synthetic" / "change_calendar.csv",
                       parse_dates=["start_time", "end_time"])


def calendar_mask(frame, calendar):
    """Boolean over `frame`: is this sample inside an announced change window for its port?

    A change filed against a device covers every port on that device. Resolving scope this way
    is the difference between suppressing one port and suppressing a switch.
    """
    mask = np.zeros(len(frame), bool)
    for row in calendar.itertuples():
        scope = ((frame["port_id"] == row.scope) | (frame["device_id"] == row.scope)).to_numpy()
        window = frame["timestamp"].between(row.start_time, row.end_time).to_numpy()
        mask |= scope & window
    return mask


def calendar_reason(frame, calendar):
    """The change_id covering each sample, or an empty string. Evidence, not just a flag."""
    reason = np.array([""] * len(frame), dtype=object)
    for row in calendar.itertuples():
        scope = ((frame["port_id"] == row.scope) | (frame["device_id"] == row.scope)).to_numpy()
        window = frame["timestamp"].between(row.start_time, row.end_time).to_numpy()
        hit = scope & window & (reason == "")
        reason[hit] = row.change_id
    return reason


def engineer_features(frame, cadence_s=CADENCE_S):
    """The eleven features, appended to a copy of the frame.

    Volume features are rates so that a change of cadence does not change their meaning. The
    three composition features are ratios, which makes them independent of volume by
    construction and hypersensitive to it in practice: their normal band is narrow, so a volume
    move that leaves the numerator alone still lands as a large deviation. Section 9 of the
    notebook is about what that does to attribution.
    """
    f = frame.copy()
    eps = 1e-9
    pkts_in = f["INUCASTPKTS"] + f["INNUCASTPKTS"]
    pkts_out = f["OUTUCASTPKTS"] + f["OUTNUCASTPKTS"]
    pkts = pkts_in + pkts_out
    octets = f["INOCTETS"] + f["OUTOCTETS"]

    f["in_bps"] = f["INOCTETS"] * 8 / cadence_s
    f["out_bps"] = f["OUTOCTETS"] * 8 / cadence_s
    f["in_pps"] = pkts_in / cadence_s
    f["out_pps"] = pkts_out / cadence_s
    f["avg_pkt_bytes"] = octets / (pkts + eps)
    f["broadcast_ratio"] = (f["INBROADCASTPKTS"] + f["OUTBROADCASTPKTS"]) / (pkts + eps)
    f["multicast_ratio"] = (f["INMULTICASTPKTS"] + f["OUTMULTICASTPKTS"]) / (pkts + eps)
    f["error_rate"] = (f["INERRORS"] + f["OUTERRORS"]) / (pkts + eps)
    f["discard_rate"] = (f["INDISCARDS"] + f["OUTDISCARDS"]) / (pkts + eps)
    f["unknown_proto_pps"] = f["INUNKNOWNPROTOS"] / cadence_s
    f["tx_ratio"] = f["OUTOCTETS"] / (octets + eps)
    return f


def counterfactual_normal(frame):
    """For every row, what each raw counter typically reads at that port and hour of the week.

    Built from normal-labelled rows only, so an incident window gets the value its own port
    would have shown had nothing happened. This is a reconstruction rather than a measurement,
    and it is only as good as the seasonal model behind it, which here is a per-bucket median.
    """
    bucket = time_of_week(frame["timestamp"])
    normal = frame["event_label"].eq("normal").to_numpy()
    out = frame.copy()
    out[RAW_COLUMNS] = out[RAW_COLUMNS].astype(float)
    for _, group in frame.groupby("port_id", sort=True):
        idx = group.index.to_numpy()
        b, n = bucket[idx], normal[idx]
        if not n.any():
            raise ValueError("a port has no normal rows; cannot build a counterfactual")
        for column in RAW_COLUMNS:
            values = group[column].to_numpy(float)
            table = np.full(168, np.median(values[n]))
            for k in range(168):
                rows = n & (b == k)
                if rows.any():
                    table[k] = np.median(values[rows])
            out.loc[idx, column] = table[b]
    return out


def attenuate_events(frame, counterfactual, strength):
    """Shrink every labelled incident toward what normal would have been at that moment.

    `strength` of 1.0 returns the file unchanged and 0.0 erases every incident. Anything between
    scales how far the counters travelled from their counterfactual, which is a severity dial.

    The blend is applied to the raw counters and the features are then rebuilt from them, so
    packet totals, byte totals and every ratio stay algebraically consistent with each other. A
    weakened incident is a smaller incident of the same kind, not an arithmetically impossible
    port. Attenuating the engineered features directly is the mistake this exists to prevent.
    """
    if not 0.0 <= strength <= 1.0:
        raise ValueError(f"strength must lie in [0, 1], got {strength}")
    out = frame.copy()
    out[RAW_COLUMNS] = out[RAW_COLUMNS].astype(float)
    hit = frame["event_label"].ne("normal").to_numpy()
    base = counterfactual.loc[hit, RAW_COLUMNS].to_numpy(float)
    observed = frame.loc[hit, RAW_COLUMNS].to_numpy(float)
    out.loc[hit, RAW_COLUMNS] = base + strength * (observed - base)
    return out


def time_of_week(timestamps):
    """Bucket key for the seasonal profile: hour of the week, 0 to 167.

    Hour of the day alone would be wrong on this fleet. The weekday mean sits near 21 Mbit/s and
    the weekend mean near 12, so a Saturday afternoon judged against a weekday afternoon profile
    reads as a permanent 40% drop. The autocorrelation says the same thing: 0.82 at one day and
    0.71 at seven, so both periods are real and only the longer one contains the shorter.
    """
    ts = pd.to_datetime(pd.Series(timestamps).reset_index(drop=True))
    return (ts.dt.dayofweek * 24 + ts.dt.hour).to_numpy()
