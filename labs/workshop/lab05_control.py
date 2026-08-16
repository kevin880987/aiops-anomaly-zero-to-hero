#!/usr/bin/env python3
"""Cross-platform control and preflight CLI for the Lab05 Compose stack."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra" / "lab05"
COMPOSE = ["docker", "compose", "-f", str(INFRA / "compose.yaml")]
SCENARIOS = ("P1", "P2", "P3", "P4", "full_incident")
MAX_SPEED = 600.0
DEFAULT_PORTS = {
    "replayer": 9200,
    "prometheus": 9090,
    "alertmanager": 9093,
    "receiver": 9300,
    "grafana": 3000,
}


def _load_dotenv(path: Path = INFRA / ".env") -> None:
    """Load simple KEY=VALUE settings without overriding the shell environment."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _port(component: str) -> int:
    key = f"LAB05_{component.upper()}_PORT"
    return int(os.getenv(key, str(DEFAULT_PORTS[component])))


def _url(component: str, path: str) -> str:
    return f"http://localhost:{_port(component)}{path}"


def validate_speed(speed: float) -> float:
    value = float(speed)
    if not 0 < value <= MAX_SPEED:
        raise ValueError(f"Replay speed must be greater than 0 and at most {MAX_SPEED:g}")
    return value


def replay_interval_seconds(speed: float, source_cadence_seconds: float = 300.0) -> float:
    return source_cadence_seconds / validate_speed(speed)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control the Lab05 production-like alert pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="check Docker and every HTTP component")
    subparsers.add_parser("check", help="validate Prometheus and Alertmanager YAML")
    subparsers.add_parser("reload", help="validate and reload active YAML")
    start = subparsers.add_parser("start", help="start one replay scenario")
    start.add_argument("scenario", choices=SCENARIOS)
    start.add_argument("--speed", type=float, default=float(os.getenv("LAB05_REPLAY_SPEED", "300")))
    subparsers.add_parser("status", help="show replay state and source clock")
    subparsers.add_parser("reset", help="return the replayer to idle")
    subparsers.add_parser("restore-config", help="restore only Lab05 active YAML from baselines")
    return parser.parse_args(argv)


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=3) as response:
            body = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach {url}: {error.reason}") from error
    return json.loads(body or b"null")


def request_ok(url: str, *, method: str = "GET") -> None:
    """Require a successful HTTP response without assuming a body format."""
    request = Request(url, method=method)
    try:
        with urlopen(request, timeout=3):
            return
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach {url}: {error.reason}") from error


def _run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=False,
        shell=False,
    )


def check_configs() -> int:
    prometheus_dir = str(INFRA / "prometheus")
    alertmanager_dir = str(INFRA / "alertmanager")
    commands = [
        [
            "docker", "run", "--rm", "--entrypoint", "/bin/promtool",
            "-v", f"{prometheus_dir}:/etc/prometheus:ro",
            "prom/prometheus:v3.13.2", "check", "config", "/etc/prometheus/prometheus.yml",
        ],
        [
            "docker", "run", "--rm", "--entrypoint", "/bin/amtool",
            "-v", f"{alertmanager_dir}:/config:ro",
            "prom/alertmanager:v0.32.1", "check-config", "/config/alertmanager.yml",
        ],
    ]
    for command in commands:
        result = _run(command)
        if result.returncode:
            return result.returncode
    return 0


def reload_configs() -> int:
    result = check_configs()
    if result:
        print("Configuration is invalid; running services were not reloaded.", file=sys.stderr)
        return result
    for component in ("prometheus", "alertmanager"):
        try:
            request_ok(_url(component, "/-/reload"), method="POST")
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 1
    print("Prometheus and Alertmanager reloaded validated configuration.")
    return 0


def restore_config(infra: Path = INFRA) -> list[str]:
    targets = ["prometheus/rules.yml", "alertmanager/alertmanager.yml"]
    for relative in targets:
        active = infra / relative
        baseline = active.with_name(active.stem + ".baseline" + active.suffix)
        shutil.copyfile(baseline, active)
    return targets


def health_report() -> int:
    rows: list[tuple[str, str, str]] = []
    docker = _run(["docker", "info"], capture=True)
    rows.append(("Docker", "PASS" if docker.returncode == 0 else "FAIL", "docker info"))
    endpoints = {
        "Replayer": ("replayer", "/-/healthy"),
        "Prometheus": ("prometheus", "/-/healthy"),
        "Alertmanager": ("alertmanager", "/-/healthy"),
        "Receiver": ("receiver", "/-/healthy"),
        "Grafana": ("grafana", "/api/health"),
    }
    for label, (component, path) in endpoints.items():
        url = _url(component, path)
        try:
            request_ok(url)
            rows.append((label, "PASS", url))
        except RuntimeError as error:
            rows.append((label, "FAIL", str(error)))
    width = max(len(row[0]) for row in rows)
    for component, state, detail in rows:
        print(f"{component:<{width}}  {state:<4}  {detail}")
    if any(state == "FAIL" for _, state, _ in rows):
        print(f"Start the stack with: docker compose -f {INFRA / 'compose.yaml'} up -d --build")
        print("If a port is occupied by native Prometheus/Grafana, change its LAB05_*_PORT in infra/lab05/.env.")
        return 1
    return 0


def print_status() -> int:
    try:
        status = request_json(_url("replayer", "/api/status"))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if isinstance(status, dict) and status.get("speed"):
        print(f"Source cadence: 300 s; replay interval: {300 / float(status['speed']):.3f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = parse_args(argv)
    if args.command == "health":
        return health_report()
    if args.command == "check":
        return check_configs()
    if args.command == "reload":
        return reload_configs()
    if args.command == "restore-config":
        restored = restore_config()
        print("Restored: " + ", ".join(restored))
        return check_configs()
    if args.command == "status":
        return print_status()
    if args.command == "start":
        try:
            speed = validate_speed(args.speed)
            result = request_json(
                _url("replayer", "/api/replays"),
                method="POST",
                payload={"scenario_id": args.scenario, "speed": speed},
            )
        except (ValueError, RuntimeError) as error:
            print(error, file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"One five-minute source point now takes {replay_interval_seconds(speed):.3f} wall-clock seconds.")
        return 0
    if args.command == "reset":
        try:
            result = request_json(_url("replayer", "/api/reset"), method="POST", payload={})
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
