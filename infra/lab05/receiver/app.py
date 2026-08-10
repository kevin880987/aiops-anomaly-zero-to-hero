#!/usr/bin/env python3
"""Local Alertmanager webhook receiver with durable lab metrics."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _escape_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _metric_labels(key: tuple[str, str, str, str, str]) -> str:
    names = ("receiver", "scenario", "run_id", "severity", "status")
    return "{" + ",".join(f'{name}="{_escape_label(value)}"' for name, value in zip(names, key)) + "}"


class NotificationStore:
    """Append-only notification history and derived Prometheus counters."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._records: list[dict[str, object]] = []
        self._notification_counts: Counter = Counter()
        self._alert_counts: Counter = Counter()
        self._last_received: dict[tuple[str, str, str, str, str], float] = {}
        self._view_cursor = 0.0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._add_record(json.loads(line))

    @staticmethod
    def _validate(receiver: str, payload: object) -> tuple[dict, list[dict]]:
        if receiver not in {"chat", "pager"}:
            raise ValueError("receiver must be chat or pager")
        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be a JSON object")
        alerts = payload.get("alerts")
        common = payload.get("commonLabels")
        if not isinstance(alerts, list) or not alerts:
            raise ValueError("webhook payload must contain at least one alert")
        if not isinstance(common, dict) or not common.get("run_id"):
            raise ValueError("webhook commonLabels must contain run_id")
        if not all(isinstance(alert, dict) and isinstance(alert.get("labels"), dict) for alert in alerts):
            raise ValueError("every webhook alert must contain labels")
        return common, alerts

    @staticmethod
    def _key(record: dict[str, object]) -> tuple[str, str, str, str, str]:
        common = record["commonLabels"]
        return (
            str(record["receiver"]),
            str(common.get("scenario", "unknown")),
            str(common["run_id"]),
            str(common.get("severity", "unknown")),
            str(record.get("status", "unknown")),
        )

    def _add_record(self, record: dict[str, object]) -> None:
        key = self._key(record)
        self._records.append(record)
        self._notification_counts[key] += 1
        self._alert_counts[key] += len(record["alerts"])
        self._last_received[key] = float(record["received_at"])

    def accept(self, receiver: str, payload: object, *, received_at: float | None = None) -> dict[str, object]:
        common, alerts = self._validate(receiver, payload)
        timestamp = time.time() if received_at is None else float(received_at)
        record = {
            "received_at": timestamp,
            "receiver": receiver,
            "status": str(payload.get("status", "unknown")),
            "groupKey": str(payload.get("groupKey", "")),
            "commonLabels": dict(common),
            "alerts": [
                {
                    "status": str(alert.get("status", "unknown")),
                    "labels": dict(alert["labels"]),
                    "annotations": dict(alert.get("annotations") or {}),
                    "startsAt": str(alert.get("startsAt", "")),
                    "endsAt": str(alert.get("endsAt", "")),
                }
                for alert in alerts
            ],
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
            self._add_record(record)
        return record

    def notification_count(self, receiver: str, run_id: str, status: str = "firing") -> int:
        with self._lock:
            return sum(
                count for key, count in self._notification_counts.items()
                if key[0] == receiver and key[2] == run_id and key[4] == status
            )

    def alert_count(self, receiver: str, run_id: str, status: str = "firing") -> int:
        with self._lock:
            return sum(
                count for key, count in self._alert_counts.items()
                if key[0] == receiver and key[2] == run_id and key[4] == status
            )

    def records(self, run_id: str | None = None) -> list[dict[str, object]]:
        with self._lock:
            records = self._records if run_id is None else [
                record for record in self._records
                if record["commonLabels"].get("run_id") == run_id
            ]
            return list(reversed(records))

    def reset_view(self) -> float:
        with self._lock:
            self._view_cursor = time.time()
            return self._view_cursor

    def render_metrics(self) -> str:
        with self._lock:
            lines = [
                "# HELP lab05_receiver_up Whether the notification receiver is healthy.",
                "# TYPE lab05_receiver_up gauge",
                "lab05_receiver_up 1.0",
                "# HELP lab05_notifications_total Alertmanager webhook deliveries.",
                "# TYPE lab05_notifications_total counter",
            ]
            for key in sorted(self._notification_counts):
                lines.append(f"lab05_notifications_total{_metric_labels(key)} {self._notification_counts[key]}")
            lines.extend([
                "# HELP lab05_notification_alerts_total Alert objects contained in webhook deliveries.",
                "# TYPE lab05_notification_alerts_total counter",
            ])
            for key in sorted(self._alert_counts):
                lines.append(f"lab05_notification_alerts_total{_metric_labels(key)} {self._alert_counts[key]}")
            lines.extend([
                "# HELP lab05_last_notification_received_timestamp_seconds Most recent webhook wall-clock timestamp.",
                "# TYPE lab05_last_notification_received_timestamp_seconds gauge",
            ])
            for key in sorted(self._last_received):
                lines.append(
                    f"lab05_last_notification_received_timestamp_seconds{_metric_labels(key)} {self._last_received[key]}"
                )
            return "\n".join(lines) + "\n"


class ReceiverHandler(BaseHTTPRequestHandler):
    store: NotificationStore

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            body = self.store.render_metrics().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/notifications":
            run_id = parse_qs(parsed.query).get("run_id", [None])[0]
            self._json(HTTPStatus.OK, self.store.records(run_id))
        elif parsed.path == "/-/healthy":
            self._json(HTTPStatus.OK, {"status": "healthy"})
        elif parsed.path == "/":
            self._json(HTTPStatus.OK, {"service": "Lab05 notification receiver", "api": "/api/notifications"})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"null")
            if parsed.path in {"/webhook/chat", "/webhook/pager"}:
                receiver = parsed.path.rsplit("/", 1)[-1]
                record = self.store.accept(receiver, payload)
                self._json(HTTPStatus.OK, {"accepted": True, "received_at": record["received_at"]})
            elif parsed.path == "/api/reset-view":
                self._json(HTTPStatus.OK, {"view_cursor": self.store.reset_view()})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})


def main() -> None:
    history = Path(os.getenv("LAB05_NOTIFICATION_HISTORY", "/data/notifications.jsonl"))
    port = int(os.getenv("LAB05_RECEIVER_PORT", "9300"))
    ReceiverHandler.store = NotificationStore(history)
    ThreadingHTTPServer(("0.0.0.0", port), ReceiverHandler).serve_forever()


if __name__ == "__main__":
    main()
