#!/usr/bin/env python3
"""Validate the cloned course repository and local runtime prerequisites.

This script is intentionally read-only. It checks files, Python packages, and
optional local services, then prints beginner-facing next steps.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import ast
import json
import platform
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]

REQUIRED_FILES = [
    "COURSE_GUIDE.md",
    "environment.yml",
    "infra/exporter.py",
    "data/synthetic/synthetic_rrd_metrics.csv",
    "data/synthetic/synthetic_event_catalog.csv",
    "infra/prometheus/prometheus.yml",
    "infra/prometheus/prometheus.windows.yml",
    "infra/prometheus/alerts.yml",
    "infra/grafana/dashboards/network_metrics.json",
    "labs/README.md",
    "labs/getting-started/README.md",
    "labs/getting-started/01a-setup-macos-python-environment.md",
    "labs/getting-started/01b-setup-linux-python-environment.md",
    "labs/getting-started/01c-setup-windows-python-environment.md",
    "labs/getting-started/02-install-prometheus.md",
    "labs/getting-started/03-setup-grafana-cloud.md",
    "labs/getting-started/04-install-node-exporter.md",
    "labs/getting-started/05-readiness-check.md",
    "labs/workshop/00_observability_stack_and_promql.ipynb",
    "labs/self-study/00_observability_stack.ipynb",
]

REQUIRED_PACKAGES = {
    "numpy": "1.26",
    "pandas": "2.0",
    "scikit-learn": "1.4",
    "matplotlib": "3.9",
    "jupyterlab": "4.3",
    "ipykernel": "6.29",
    "prometheus-client": "0.20",
}

REQUIRED_MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "matplotlib": "matplotlib",
    "jupyterlab": "jupyterlab",
    "ipykernel": "ipykernel",
    "prometheus-client": "prometheus_client",
}

OPTIONAL_ENDPOINTS = [
    ("course exporter", "http://localhost:8000/metrics"),
    ("Prometheus", "http://localhost:9090/-/ready"),
    ("Prometheus", "http://localhost:9090/-/ready"),
    ("node_exporter", "http://localhost:9100/metrics"),
    ("windows_exporter", "http://localhost:9182/metrics"),
]


def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in value.replace("-", ".").split("."):
        if part.isdigit():
            parts.append(int(part))
            continue
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            parts.append(int(digits))
        break
    return tuple(parts)


def check_file(path: str) -> tuple[bool, str]:
    full_path = REPO_ROOT / path
    if full_path.exists():
        return True, f"ok file: {path}"
    return False, f"missing file: {path}"


def check_json(path: str) -> tuple[bool, str]:
    full_path = REPO_ROOT / path
    try:
        json.loads(full_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, f"invalid JSON: {path} ({exc})"
    return True, f"ok JSON: {path}"


def check_dashboard_metric_refs() -> tuple[bool, str]:
    exporter_source = ast.parse((REPO_ROOT / "infra/exporter.py").read_text(encoding="utf-8"))
    metric_cols = None
    for node in exporter_source.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "METRIC_COLS":
                metric_cols = ast.literal_eval(node.value)
                break
    if metric_cols is None:
        return False, "METRIC_COLS not found in exporter.py"

    emitted = {f"network_rrd_{col.lower()}" for col in metric_cols}
    emitted |= {"network_rrd_simulated_timestamp", "network_rrd_event"}

    dashboard = json.loads((REPO_ROOT / "infra/grafana/dashboards/network_metrics.json").read_text(encoding="utf-8"))
    refs: set[str] = set()
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            refs.update(re.findall(r"network_rrd_[a-z0-9_]+", target.get("expr", "")))
    for template in dashboard.get("templating", {}).get("list", []):
        refs.update(re.findall(r"network_rrd_[a-z0-9_]+", template.get("definition", "")))

    missing = sorted(refs - emitted)
    if missing:
        return False, f"dashboard references metrics not emitted by exporter.py: {', '.join(missing)}"
    return True, "ok dashboard metric references match exporter.py"


def check_packages() -> list[tuple[bool, str]]:
    checks: list[tuple[bool, str]] = []
    if sys.version_info < (3, 12):
        checks.append((False, f"Python >= 3.12 required; found {platform.python_version()}"))
    else:
        checks.append((True, f"ok Python: {platform.python_version()}"))

    for package, minimum in REQUIRED_PACKAGES.items():
        module_name = REQUIRED_MODULES[package]
        if importlib.util.find_spec(module_name) is None:
            checks.append((False, f"missing Python package: {package}"))
            continue
        version = importlib.metadata.version(package)
        if version_tuple(version) < version_tuple(minimum):
            checks.append((False, f"{package} >= {minimum} required; found {version}"))
            continue
        checks.append((True, f"ok package: {package} {version}"))
    return checks


def endpoint_status(name: str, url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if 200 <= response.status < 500:
                return True, f"reachable service: {name} ({url})"
            return False, f"service returned HTTP {response.status}: {name} ({url})"
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return False, f"not running yet: {name} ({url})"


def main() -> int:
    repo_only = "--repo-only" in sys.argv[1:]
    failures = 0
    print(f"Repository root: {REPO_ROOT}")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print("")

    print("Required repository files")
    for path in REQUIRED_FILES:
        ok, message = check_file(path)
        print(f"  [{'OK' if ok else '!!'}] {message}")
        failures += 0 if ok else 1

    print("")
    print("Notebook and dashboard JSON")
    json_paths = list((REPO_ROOT / "labs").rglob("*.ipynb"))
    json_paths += list((REPO_ROOT / "data").rglob("*.ipynb"))
    json_paths += list((REPO_ROOT / "infra" / "grafana" / "dashboards").glob("*.json"))
    for full_path in sorted(json_paths):
        ok, message = check_json(str(full_path.relative_to(REPO_ROOT)))
        print(f"  [{'OK' if ok else '!!'}] {message}")
        failures += 0 if ok else 1
    ok, message = check_dashboard_metric_refs()
    print(f"  [{'OK' if ok else '!!'}] {message}")
    failures += 0 if ok else 1

    if not repo_only:
        print("")
        print("Python environment")
        for ok, message in check_packages():
            print(f"  [{'OK' if ok else '!!'}] {message}")
            failures += 0 if ok else 1

        print("")
        print("Optional local services")
        for name, url in OPTIONAL_ENDPOINTS:
            ok, message = endpoint_status(name, url)
            print(f"  [{'OK' if ok else '..'}] {message}")
    else:
        print("")
        print("Repo-only mode: skipped Python package and local service checks.")

    print("")
    if failures:
        print(f"Validation failed with {failures} required issue(s).")
        if repo_only:
            print("Fix the repository files above, then retry.")
        else:
            print("Run the platform bootstrap script from the repository root, then retry.")
        return 1

    print("Required checks passed.")
    print("If optional services are not running yet, continue with labs/getting-started/02-04.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
