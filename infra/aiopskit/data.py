"""Telemetry loading with an explicit unit contract.

The course CSV mimics an RRD export: each row holds the octet and packet totals
accumulated *within* the preceding polling interval, not a monotonic counter.
Treating those columns as Prometheus-style counters and differencing them is the
single most common way to destroy the signal before any detector sees it, so
this module refuses to guess silently. `load_telemetry` reports which reading it
applied and why.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import paths

KEY_COLUMNS = ["device_id", "port_id", "port_role"]

OCTET_COLUMNS = ["INOCTETS", "OUTOCTETS"]
PACKET_COLUMNS = [
    "INUCASTPKTS", "OUTUCASTPKTS",
    "INNUCASTPKTS", "OUTNUCASTPKTS",
    "INBROADCASTPKTS", "OUTBROADCASTPKTS",
    "INMULTICASTPKTS", "OUTMULTICASTPKTS",
]
FAULT_COLUMNS = ["INERRORS", "OUTERRORS", "INDISCARDS", "OUTDISCARDS", "INUNKNOWNPROTOS"]
RAW_COLUMNS = OCTET_COLUMNS + PACKET_COLUMNS + FAULT_COLUMNS


@dataclass
class TelemetryContract:
    """What the loader decided about the raw file, so a lab can print it."""

    cadence_s: float
    semantics: str
    monotonic_fraction: float
    n_rows: int
    n_ports: int
    span: tuple[pd.Timestamp, pd.Timestamp]
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        lo, hi = self.span
        lines = [
            f"rows            {self.n_rows:,} across {self.n_ports} ports",
            f"span            {lo}  ->  {hi}",
            f"cadence         {self.cadence_s:.0f} s per sample "
            f"({self.cadence_s / 60:.0f} min; {int(round(86400 / self.cadence_s))} samples/day)",
            f"column reading  {self.semantics}",
            f"monotonic frac  {self.monotonic_fraction:.3f} of consecutive octet steps are non-negative",
        ]
        lines += [f"note            {note}" for note in self.notes]
        return "\n".join(lines)


def infer_cadence(timestamps: pd.Series, group: pd.Series | None = None) -> float:
    """Median sampling interval in seconds, computed per series when grouped."""
    if group is None:
        deltas = timestamps.sort_values().diff().dt.total_seconds()
    else:
        frame = pd.DataFrame({"ts": timestamps, "g": group}).sort_values(["g", "ts"])
        deltas = frame.groupby("g", observed=True)["ts"].diff().dt.total_seconds()
    deltas = deltas.dropna()
    deltas = deltas[deltas > 0]
    if deltas.empty:
        raise ValueError("Cannot infer cadence: no positive timestamp differences.")
    return float(deltas.median())


def _monotonic_fraction(raw: pd.DataFrame) -> float:
    """Share of within-port steps in which INOCTETS does not decrease.

    A genuine counter is ~1.0 apart from restarts. A per-interval delta column
    sits near 0.5 because it rises and falls with the traffic itself.
    """
    steps = raw.sort_values(["port_id", "timestamp"]).groupby("port_id", observed=True)["INOCTETS"].diff()
    steps = steps.dropna()
    if steps.empty:
        return 1.0
    return float((steps >= 0).mean())


def load_telemetry(
    csv_path=None,
    ports: list[str] | None = None,
    semantics: str = "auto",
) -> tuple[pd.DataFrame, TelemetryContract]:
    """Load the course telemetry and convert every raw column to a per-second rate.

    semantics:
        "auto"     decide from the monotonicity of INOCTETS (the default)
        "delta"    each row already holds the interval total; divide by cadence
        "counter"  each row holds a cumulative total; difference, then divide

    Returns a long frame keyed by (device_id, port_id, timestamp) plus the
    contract the loader applied.
    """
    csv_path = paths.TELEMETRY_CSV if csv_path is None else csv_path
    raw = pd.read_csv(csv_path, parse_dates=["timestamp"])
    if ports:
        raw = raw[raw["port_id"].isin(ports)]
    raw = raw.sort_values(["device_id", "port_id", "timestamp"]).reset_index(drop=True)

    cadence = infer_cadence(raw["timestamp"], raw["port_id"])
    mono = _monotonic_fraction(raw)
    notes: list[str] = []

    if semantics == "auto":
        semantics = "counter" if mono > 0.97 else "delta"
        notes.append(
            f"reading chosen automatically: {mono:.1%} of octet steps are non-negative, "
            f"{'consistent with a cumulative counter' if semantics == 'counter' else 'so the column is a per-interval total, not a counter'}"
        )
    if semantics == "counter" and mono < 0.97:
        notes.append(
            "counter reading forced on a non-monotonic column; differencing will clip "
            "roughly half the samples to zero"
        )

    per_port = raw.groupby(["device_id", "port_id"], observed=True)

    def to_rate(column: str) -> pd.Series:
        values = raw[column].astype(float)
        if semantics == "counter":
            values = per_port[column].diff().astype(float).clip(lower=0)
        return values / cadence

    out = pd.DataFrame({
        "timestamp": raw["timestamp"],
        "device_id": raw["device_id"].astype(str),
        "port_id": raw["port_id"].astype(str),
        "port_role": raw["port_role"].astype(str),
        "event_label": raw.get("event_label", pd.Series("normal", index=raw.index)).astype(str),
        "event_id": raw.get("event_id", pd.Series(pd.NA, index=raw.index)).astype("string").fillna(""),
    })
    for column in RAW_COLUMNS:
        if column in raw.columns:
            out[column.lower() + "_ps"] = to_rate(column)

    out = _add_derived_features(out)
    if semantics == "counter":
        # The first sample of each series has no predecessor, so its differenced
        # rate is a fabricated zero. Drop it rather than let it anchor a baseline.
        first_of_series = out.groupby(["device_id", "port_id"], observed=True).cumcount() == 0
        out = out[~first_of_series].reset_index(drop=True)

    contract = TelemetryContract(
        cadence_s=cadence,
        semantics=semantics,
        monotonic_fraction=mono,
        n_rows=len(out),
        n_ports=int(out["port_id"].nunique()),
        span=(out["timestamp"].min(), out["timestamp"].max()),
        notes=notes,
    )
    return out, contract


def _add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Operationally meaningful combinations of the per-second rates.

    Each one is here because it is the most sensitive view of a specific failure
    mode; see the feature-to-fault table in Lab 01.
    """
    eps = 1e-9
    rx = df["inoctets_ps"]
    tx = df["outoctets_ps"]
    ucast = df["inucastpkts_ps"] + df["outucastpkts_ps"]
    nucast = df.get("innucastpkts_ps", 0) + df.get("outnucastpkts_ps", 0)
    bcast = df["inbroadcastpkts_ps"] + df["outbroadcastpkts_ps"]
    mcast = df["inmulticastpkts_ps"] + df["outmulticastpkts_ps"]
    errors = df["inerrors_ps"] + df["outerrors_ps"]
    discards = df["indiscards_ps"] + df["outdiscards_ps"]
    packets = ucast + nucast

    df["traffic_bps"] = rx + tx
    df["packets_pps"] = packets
    df["errors_pps"] = errors
    df["discards_pps"] = discards
    df["broadcast_pps"] = bcast
    df["multicast_pps"] = mcast
    df["unknown_proto_pps"] = df.get("inunknownprotos_ps", 0.0)

    df["error_rate"] = errors / (packets + eps)
    df["discard_rate"] = discards / (packets + eps)
    df["tx_ratio"] = tx / (rx + tx + eps)
    df["avg_pkt_bytes"] = (rx + tx) / (packets + bcast + mcast + eps)
    df["broadcast_ratio"] = bcast / (packets + bcast + mcast + eps)
    df["multicast_ratio"] = mcast / (packets + bcast + mcast + eps)
    return df


def load_events(telemetry: pd.DataFrame, catalog_path=None) -> pd.DataFrame:
    """Ground-truth event windows, derived per port from the label column.

    The published catalog records `MULTI` for events that hit several ports at
    once. Deriving windows from the telemetry labels instead gives one row per
    (event, port), which is what event-level scoring needs.
    """
    labelled = telemetry[telemetry["event_label"] != "normal"].copy()
    if labelled.empty:
        return pd.DataFrame(
            columns=["event_id", "event_type", "device_id", "port_id", "port_role",
                     "start", "end", "n_points", "description"]
        )

    grouped = labelled.groupby(["event_id", "event_label", "device_id", "port_id", "port_role"], observed=True)
    events = grouped.agg(start=("timestamp", "min"), end=("timestamp", "max"), n_points=("timestamp", "size"))
    events = events.reset_index().rename(columns={"event_label": "event_type"})

    catalog_path = paths.EVENT_CATALOG_CSV if catalog_path is None else catalog_path
    try:
        catalog = pd.read_csv(catalog_path)
        descriptions = dict(zip(catalog["event_id"].astype(str), catalog["description"].astype(str)))
    except (FileNotFoundError, KeyError):
        descriptions = {}
    events["description"] = events["event_id"].astype(str).map(descriptions).fillna("")
    return events.sort_values("start").reset_index(drop=True)


def load_change_calendar(path=None) -> pd.DataFrame:
    """Planned changes and maintenance windows.

    Some ground-truth events are expected consequences of planned work. An alert
    fired inside one of these windows is a suppression failure, not a detection
    success, which is why the calendar is a first-class input rather than a note
    in a runbook.
    """
    path = paths.CHANGE_CALENDAR_CSV if path is None else path
    calendar = pd.read_csv(path, parse_dates=["start_time", "end_time"])
    calendar = calendar.rename(columns={"start_time": "start", "end_time": "end"})
    return calendar.sort_values("start").reset_index(drop=True)


def scope_matches(scope: str, device_id: str, port_id: str) -> bool:
    """A calendar scope is `ALL`, a device id, or a port id."""
    scope = str(scope)
    return scope in ("ALL", "*") or scope == device_id or scope == port_id


def truth_mask(frame: pd.DataFrame, events: pd.DataFrame) -> pd.Series:
    """Boolean per-sample ground truth aligned to `frame`."""
    mask = pd.Series(False, index=frame.index)
    for event in events.itertuples():
        hit = (
            (frame["port_id"] == event.port_id)
            & (frame["timestamp"] >= event.start)
            & (frame["timestamp"] <= event.end)
        )
        mask |= hit
    return mask


def in_change_window(frame: pd.DataFrame, calendar: pd.DataFrame) -> pd.Series:
    """Boolean per-sample flag: does this sample fall inside a planned change?"""
    mask = pd.Series(False, index=frame.index)
    for change in calendar.itertuples():
        scoped = frame.apply(
            lambda row: scope_matches(change.scope, row["device_id"], row["port_id"]), axis=1
        )
        mask |= scoped & (frame["timestamp"] >= change.start) & (frame["timestamp"] <= change.end)
    return mask


def split_events(events: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate events a detector must catch from events it must stay quiet about.

    Both look identical in the telemetry. What distinguishes them is a record in
    the change calendar saying someone planned this. Unit 03 makes the same
    point about change points: a structural break is an entry point for
    investigation, not a verdict, and correlating it against deployment and
    maintenance records is how the verdict gets reached.

    Returns (incidents, planned).
    """
    planned_mask = pd.Series(False, index=events.index)
    matched_change = pd.Series("", index=events.index)
    for change in calendar.itertuples():
        for i, event in events.iterrows():
            if planned_mask.loc[i]:
                continue
            if not scope_matches(change.scope, event["device_id"], event["port_id"]):
                continue
            if event["start"] <= change.end and event["end"] >= change.start:
                planned_mask.loc[i] = True
                matched_change.loc[i] = str(change.change_id)

    incidents = events[~planned_mask].reset_index(drop=True)
    planned = events[planned_mask].copy()
    planned["change_id"] = matched_change[planned_mask].to_numpy()
    return incidents, planned.reset_index(drop=True)


def single_port(telemetry: pd.DataFrame, port_id: str | None = None) -> pd.DataFrame:
    """One port as a contiguous, time-sorted frame for single-series work."""
    if port_id is None:
        port_id = telemetry["port_id"].value_counts().index[0]
    frame = telemetry[telemetry["port_id"] == port_id].copy()
    return frame.sort_values("timestamp").reset_index(drop=True)


def synthetic_wave(n: int = 240, cadence_s: int = 60, seed: int = 7) -> pd.DataFrame:
    """A deliberately trivial series for the Lab 00 plumbing check.

    A daily-shaped sine, gaussian noise, and one injected step so that a cadet
    can tell at a glance whether the number reaching Grafana is the number the
    notebook computed.
    """
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.utcnow().tz_localize(None).floor("min")
    ts = pd.date_range(end - pd.Timedelta(seconds=cadence_s * (n - 1)), periods=n, freq=f"{cadence_s}s")
    phase = np.linspace(0, 4 * np.pi, n)
    value = 50 + 20 * np.sin(phase) + rng.normal(0, 2.0, n)
    value[int(n * 0.7): int(n * 0.78)] += 45.0
    return pd.DataFrame({
        "timestamp": ts,
        "device_id": "toy-device",
        "port_id": "toy-port",
        "port_role": "demo",
        "event_label": "normal",
        "toy_value": value,
    })
