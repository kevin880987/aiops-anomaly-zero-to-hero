#!/usr/bin/env python3
"""Replay five-minute Lab05 source data as current Prometheus metrics."""

from __future__ import annotations

import csv
import json
import math
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable


SOURCE_CADENCE_SECONDS = 300.0


class ReplayConflict(RuntimeError):
    """Raised when a second replay would replace an active run."""


@dataclass(frozen=True)
class ReplayStatus:
    state: str
    scenario_id: str | None
    run_id: str | None
    sample_index: int | None
    source_timestamp: str | None
    speed: float
    replay_interval_seconds: float
    progress_ratio: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _escape_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**values: object) -> str:
    return "{" + ",".join(f'{key}="{_escape_label(value)}"' for key, value in values.items()) + "}"


class ReplayEngine:
    """Clock-driven replay state with no background worker."""

    def __init__(
        self,
        metrics_path: Path,
        events_path: Path,
        *,
        clock: Callable[[], float] = time.monotonic,
        scrape_interval_seconds: float = 0.25,
    ):
        self._clock = clock
        self._scrape_interval = float(scrape_interval_seconds)
        self._lock = threading.RLock()
        self._scenarios = self._load_metrics(metrics_path)
        self._events = self._load_events(events_path)
        self._run_counts = {scenario: 0 for scenario in self._scenarios}
        self._scenario_id: str | None = None
        self._run_id: str | None = None
        self._started_at = 0.0
        self._speed = 0.0
        self._interval = 0.0

    @staticmethod
    def _load_metrics(path: Path) -> dict[str, list[list[dict[str, object]]]]:
        scenarios: dict[str, dict[int, list[dict[str, object]]]] = {}
        with Path(path).open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, object] = dict(raw)
                row["sample_index"] = int(raw["sample_index"])
                for key in ("mahalanobis_score", "lof_score", "packet_loss_ratio"):
                    row[key] = float(raw[key])
                row["service_up"] = int(raw["service_up"])
                row["maintenance_active"] = int(raw["maintenance_active"])
                scenarios.setdefault(raw["scenario_id"], {}).setdefault(int(raw["sample_index"]), []).append(row)
        if not scenarios:
            raise ValueError("Replay metrics file is empty")
        result: dict[str, list[list[dict[str, object]]]] = {}
        for scenario, by_index in scenarios.items():
            expected = list(range(max(by_index) + 1))
            if sorted(by_index) != expected:
                raise ValueError(f"Scenario {scenario} has non-contiguous sample indices")
            result[scenario] = [by_index[index] for index in expected]
        return result

    @staticmethod
    def _load_events(path: Path) -> dict[str, list[dict[str, object]]]:
        events: dict[str, list[dict[str, object]]] = {}
        with Path(path).open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                event: dict[str, object] = dict(raw)
                event["start_time"] = datetime.fromisoformat(raw["start_time"])
                event["end_time"] = datetime.fromisoformat(raw["end_time"])
                event["maintenance"] = _parse_bool(raw["maintenance"])
                events.setdefault(raw["scenario_id"], []).append(event)
        return events

    @property
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(self._scenarios)

    def start(self, scenario_id: str, speed: float) -> ReplayStatus:
        speed = float(speed)
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("Replay speed must be a positive finite number")
        interval = SOURCE_CADENCE_SECONDS / speed
        if interval < 2 * self._scrape_interval:
            maximum = SOURCE_CADENCE_SECONDS / (2 * self._scrape_interval)
            raise ValueError(
                f"Replay interval must cover at least two scrape intervals; maximum speed is {maximum:g}"
            )
        with self._lock:
            if self._scenario_id is not None and self._snapshot().state == "running":
                raise ReplayConflict("A replay is already running; reset it before starting another")
            if scenario_id not in self._scenarios:
                raise KeyError(f"Unknown scenario {scenario_id!r}; choose from {', '.join(self.scenario_names)}")
            self._run_counts[scenario_id] += 1
            self._scenario_id = scenario_id
            self._run_id = f"{scenario_id}-{self._run_counts[scenario_id]:03d}"
            self._started_at = self._clock()
            self._speed = speed
            self._interval = interval
            return self._snapshot()

    def reset(self) -> ReplayStatus:
        with self._lock:
            self._scenario_id = None
            self._run_id = None
            self._started_at = 0.0
            self._speed = 0.0
            self._interval = 0.0
            return self._snapshot()

    def _snapshot(self) -> ReplayStatus:
        if self._scenario_id is None:
            return ReplayStatus("idle", None, None, None, None, 0.0, 0.0, 0.0)
        samples = self._scenarios[self._scenario_id]
        elapsed = max(0.0, self._clock() - self._started_at)
        raw_index = int(elapsed // self._interval)
        index = min(raw_index, len(samples) - 1)
        state = "complete" if raw_index >= len(samples) - 1 else "running"
        timestamp = str(samples[index][0]["source_timestamp"])
        progress = index / (len(samples) - 1) if len(samples) > 1 else 1.0
        return ReplayStatus(
            state,
            self._scenario_id,
            self._run_id,
            index,
            timestamp,
            self._speed,
            self._interval,
            progress,
        )

    def status(self) -> ReplayStatus:
        with self._lock:
            return self._snapshot()

    def _current_rows(self, status: ReplayStatus) -> list[dict[str, object]]:
        if status.scenario_id is None or status.sample_index is None:
            return []
        return self._scenarios[status.scenario_id][status.sample_index]

    def render_metrics(self) -> str:
        with self._lock:
            status = self._snapshot()
            lines = [
                "# HELP lab05_replayer_up Whether the replay service is healthy.",
                "# TYPE lab05_replayer_up gauge",
                "lab05_replayer_up 1.0",
            ]
            if status.scenario_id is None:
                return "\n".join(lines) + "\n"
            common = {"scenario": status.scenario_id, "run_id": status.run_id}
            lines.extend([
                "# HELP lab05_replay_source_timestamp_seconds Current source-data Unix timestamp.",
                "# TYPE lab05_replay_source_timestamp_seconds gauge",
                f"lab05_replay_source_timestamp_seconds{_labels(**common)} {datetime.fromisoformat(status.source_timestamp).timestamp()}",
                "# HELP lab05_replay_speed Source-time replay acceleration factor.",
                "# TYPE lab05_replay_speed gauge",
                f"lab05_replay_speed{_labels(**common)} {status.speed}",
                "# HELP lab05_replay_progress_ratio Fraction of scenario source points reached.",
                "# TYPE lab05_replay_progress_ratio gauge",
                f"lab05_replay_progress_ratio{_labels(**common)} {status.progress_ratio}",
                "# HELP lab05_anomaly_score Precomputed detector score.",
                "# TYPE lab05_anomaly_score gauge",
            ])
            for row in self._current_rows(status):
                base = {
                    "site": row["site"], "target": row["target"],
                    "scenario": status.scenario_id, "run_id": status.run_id,
                    "maintenance": str(bool(row["maintenance_active"])).lower(),
                }
                for detector, column in (("mahalanobis", "mahalanobis_score"), ("lof", "lof_score")):
                    labels = dict(base)
                    labels["detector"] = detector
                    ordered = {
                        "site": labels["site"], "target": labels["target"], "detector": labels["detector"],
                        "scenario": labels["scenario"], "run_id": labels["run_id"], "maintenance": labels["maintenance"],
                    }
                    lines.append(f"lab05_anomaly_score{_labels(**ordered)} {row[column]}")
                lines.append(f"lab05_packet_loss_ratio{_labels(**base)} {row['packet_loss_ratio']}")
                lines.append(f"lab05_service_up{_labels(**base)} {row['service_up']}")

            current = datetime.fromisoformat(status.source_timestamp)
            for event in self._events.get(status.scenario_id, []):
                if event["start_time"] <= current < event["end_time"]:
                    truth_labels = {
                        "event_type": event["event_type"], "site": "taipei-dc1", "target": event["target"],
                        "scenario": status.scenario_id, "run_id": status.run_id,
                    }
                    lines.append(f"lab05_truth_event_active{_labels(**truth_labels)} 1.0")
            return "\n".join(lines) + "\n"


class ReplayHandler(BaseHTTPRequestHandler):
    engine: ReplayEngine

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/metrics":
            body = self.engine.render_metrics().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self._json(HTTPStatus.OK, self.engine.status().as_dict())
        elif self.path == "/-/healthy":
            self._json(HTTPStatus.OK, {"status": "healthy", "scenarios": self.engine.scenario_names})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/replays":
                status = self.engine.start(payload.get("scenario_id", ""), payload.get("speed", 300))
                self._json(HTTPStatus.ACCEPTED, status.as_dict())
            elif self.path == "/api/reset":
                self._json(HTTPStatus.OK, self.engine.reset().as_dict())
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except ReplayConflict as error:
            self._json(HTTPStatus.CONFLICT, {"error": str(error)})
        except KeyError as error:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(error), "scenarios": self.engine.scenario_names})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})


def main() -> None:
    metrics_path = Path(os.getenv("LAB05_METRICS_PATH", "/data/lab05_replay_metrics.csv"))
    events_path = Path(os.getenv("LAB05_EVENTS_PATH", "/data/lab05_event_catalog.csv"))
    scrape_interval = float(os.getenv("LAB05_SCRAPE_INTERVAL_SECONDS", "0.25"))
    port = int(os.getenv("LAB05_REPLAYER_PORT", "9200"))
    ReplayHandler.engine = ReplayEngine(metrics_path, events_path, scrape_interval_seconds=scrape_interval)
    ThreadingHTTPServer(("0.0.0.0", port), ReplayHandler).serve_forever()


if __name__ == "__main__":
    main()
