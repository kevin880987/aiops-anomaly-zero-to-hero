#!/usr/bin/env python3
"""Week 6 的 Grafana 環境: 一支程式，macOS、Windows、Linux 都一樣跑。

兩本 lab 各自從一個 case 出發，所以這裡同時重播兩份:
    Lab 06 的那兩晚   (2/25 良性、2/26 越線)
    Lab 07 的那次事故 (事故 L，光路劣化引發下游重傳)

課堂上只要這一行 (在 week6 這個資料夾裡執行,也就是跟這支程式放在一起的那一層):

    python 4_grafana.py

它會照順序做五件事，中間任何一步失敗都會告訴你下一步該做什麼:

    1. 檢查 Docker 有沒有裝、Docker 的背景服務有沒有在跑
    2. 檢查兩份重播用的 CSV 在不在 (它們是兩本 notebook 各自寫出來的)
    3. 檢查四個 host port 有沒有被別的東西佔住
    4. docker compose up -d --build,然後等三個服務都健康
    5. 用預設瀏覽器打開兩張儀表板，畫面上就是上課走的那兩個 case

其他子指令:

    python 4_grafana.py health   只檢查，不啟動
    python 4_grafana.py open     只開瀏覽器
    python 4_grafana.py logs     看四個服務的紀錄
    python 4_grafana.py down     關掉 (資料留著)
    python 4_grafana.py down --clean   關掉並刪掉 Prometheus 與 Grafana 的資料
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

def _find_root() -> Path:
    """從這支程式所在的位置往上走，找到裝著 infra/stack/compose.yaml 的那一層。

    正常情況第一步就找到: 這支程式在 week6/，compose 在 week6/infra/stack/。
    還是寫成往上找，是為了萬一整個資料夾被放進更深的地方，路徑一樣算得出來。
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "infra" / "stack" / "compose.yaml").is_file():
            return candidate
    return here            # 找不到就用自己所在的資料夾，後面的檢查會報「找不到 compose.yaml」


ROOT = _find_root()
INFRA = ROOT / "infra" / "stack"
COMPOSE_FILE = INFRA / "compose.yaml"
# 兩份重播用的 CSV，各由一本 notebook 寫出來。少一份就少一張儀表板的資料。
CASE_CSVS = {
    "Lab 06 (那兩晚) ": (ROOT / "outputs" / "workshop" / "forecast_case_K.csv",
                        "2_lab06_forecasting.ipynb"),
    "Lab 07 (事故 L) ": (ROOT / "outputs" / "workshop" / "rca_case_L.csv",
                        "3_lab07_root_cause_analysis.ipynb"),
}
DASHBOARDS = {
    "Lab 06 預警": "/d/aiops-lab06-forecast/lab-06",
    "Lab 07 根因": "/d/aiops-lab07-rca/lab-07-rca",
}

# 預設 host port。被佔住的時候可以用環境變數或 infra/stack/.env 換掉。
DEFAULT_PORTS = {"replayer06": 8011, "replayer07": 8010,
                 "prometheus": 9090, "grafana": 3000}
READY_TIMEOUT_SECONDS = 240


# --------------------------------------------------------------------------- 設定

def load_dotenv(path: Path = INFRA / ".env") -> None:
    """讀 infra/stack/.env 這種簡單的 KEY=VALUE 設定，但不覆蓋 shell 裡已經設好的值。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def port_of(component: str) -> int:
    return int(os.getenv(f"WEEK6_{component.upper()}_PORT", str(DEFAULT_PORTS[component])))


def url_of(component: str, path: str = "") -> str:
    return f"http://localhost:{port_of(component)}{path}"


def dashboard_url(path: str) -> str:
    return url_of("grafana", f"{path}?from=now-15m&to=now&refresh=5s")


def all_dashboard_urls() -> dict:
    return {name: dashboard_url(path) for name, path in DASHBOARDS.items()}


# --------------------------------------------------------------------------- 小工具

def say(ok: bool | None, message: str) -> None:
    mark = {True: "[ok]  ", False: "[fail]", None: "[..]  "}[ok]
    print(f"{mark} {message}", flush=True)


def compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, cwd=str(INFRA), text=True, check=False,
                          capture_output=capture)


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (URLError, OSError, ValueError):
        return False


def port_is_free(port: int) -> bool:
    """Docker 會綁 0.0.0.0，所以就照它綁的位址試一次。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


# --------------------------------------------------------------------------- 檢查

def check_docker() -> bool:
    from shutil import which
    if which("docker") is None:
        say(False, "找不到 docker 指令。請先安裝 Docker Desktop (macOS / Windows) "
                   "或 Docker Engine (Linux) ")
        return False
    probe = subprocess.run(["docker", "info"], text=True, check=False, capture_output=True)
    if probe.returncode != 0:
        say(False, "Docker 裝好了，但背景服務沒有在跑。請先打開 Docker Desktop，"
                   "等它的圖示變成執行中再跑一次")
        return False
    say(True, "Docker 可以用")
    return True


def check_case_csv() -> bool:
    """兩份重播用的 CSV 都要在。少一份就直接說是哪一本 notebook 還沒跑。"""
    ok = True
    for label, (path, notebook) in CASE_CSVS.items():
        if not path.exists():
            say(False, f"{label} 找不到 {path.relative_to(ROOT)}。"
                       f"請先把 {notebook} 從頭跑到底，它會寫出這一份")
            ok = False
            continue
        rows = sum(1 for _ in path.open(encoding="utf-8")) - 1
        say(True, f"{label} 找到 {path.relative_to(ROOT)} ({rows:,} 列) ")
    return ok


def running_services() -> set[str]:
    """這個 compose 專案目前有哪幾個服務在跑。

    port 被佔住不一定是壞事: 佔住的如果就是這個 stack 自己，那是重跑而不是衝突。
    但「有東西回應」不等於「是我們的東西」: 上一週課裝的本機 Grafana 一樣會佔住 3000
    而且一樣回得出 /api/health,所以這裡問的是 docker compose 自己，不是那個 port。"""
    probe = compose("ps", "--services", "--filter", "status=running", capture=True)
    if probe.returncode != 0:
        return set()
    return {line.strip() for line in probe.stdout.splitlines() if line.strip()}


def check_ports() -> bool:
    ours = running_services()
    all_free = True
    for name in DEFAULT_PORTS:
        port = port_of(name)
        if port_is_free(port):
            say(True, f"{name} 的 port {port} 沒有被佔用")
        elif name in ours:
            say(True, f"{name} 的 port {port} 已經是這個 stack 自己在用")
        else:
            say(False, f"{name} 的 port {port} 被別的程式佔住 (不是這個 stack) 。"
                       f"先關掉它，或在 infra/stack/.env 設 WEEK6_{name.upper()}_PORT 換一個。"
                       f"上一週課用 brew 或 systemd 裝的 Grafana / Prometheus 是最常見的原因")
            all_free = False
    return all_free


# --------------------------------------------------------------------------- 動作

def wait_until_ready(timeout: int = READY_TIMEOUT_SECONDS) -> bool:
    checks = [("Lab 06 重播程式", url_of("replayer06", "/metrics")),
              ("Lab 07 重播程式", url_of("replayer07", "/metrics")),
              ("Prometheus", url_of("prometheus", "/-/healthy")),
              ("Grafana", url_of("grafana", "/api/health"))]
    deadline = time.time() + timeout
    pending = list(checks)
    while pending and time.time() < deadline:
        still = []
        for label, url in pending:
            if http_ok(url):
                say(True, f"{label} 起來了")
            else:
                still.append((label, url))
        pending = still
        if pending:
            time.sleep(2)
    for label, _ in pending:
        say(False, f"{label} 在 {timeout} 秒內沒有起來。跑 "
                   f"`python 4_grafana.py logs` 看它說了什麼")
    return not pending


def cmd_up(args: argparse.Namespace) -> int:
    print("Week 6 Grafana 環境 (Lab 06 與 Lab 07 兩個 case) \n" + "-" * 46)
    if not check_docker():
        return 1
    if not check_case_csv():
        return 1
    if not check_ports():
        return 1
    say(None, "啟動四個服務 (第一次要先 build，會花一兩分鐘) ")
    if compose("up", "-d", "--build").returncode != 0:
        say(False, "docker compose up 失敗，上面那段輸出就是原因")
        return 1
    if not wait_until_ready():
        return 1
    for name, url in all_dashboard_urls().items():
        say(True, f"{name}: {url}")
    if not args.no_browser:
        for url in all_dashboard_urls().values():
            webbrowser.open(url)
    print("-" * 46)
    print("兩張儀表板各對應一本 lab 的 case: Lab 06 是 2/25 與 2/26 那兩晚,")
    print("Lab 07 是事故 L。重播是循環的，走完整段會從頭再來一輪。")
    print("關掉環境: python 4_grafana.py down")
    return 0


def cmd_health(_: argparse.Namespace) -> int:
    ok = check_docker()
    ok = check_case_csv() and ok
    check_ports()
    for label, url in [("Lab 06 重播程式", url_of("replayer06", "/metrics")),
                       ("Lab 07 重播程式", url_of("replayer07", "/metrics")),
                       ("Prometheus", url_of("prometheus", "/-/healthy")),
                       ("Grafana", url_of("grafana", "/api/health"))]:
        alive = http_ok(url)
        say(alive, f"{label} {'有回應' if alive else '沒有回應'} ({url}) ")
        ok = ok and alive
    return 0 if ok else 1


def cmd_open(_: argparse.Namespace) -> int:
    if not http_ok(url_of("grafana", "/api/health")):
        say(False, "Grafana 還沒有起來。先跑 python 4_grafana.py")
        return 1
    for name, url in all_dashboard_urls().items():
        say(True, f"打開 {name}: {url}")
        webbrowser.open(url)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    return compose("logs", "--tail", str(args.tail)).returncode


def cmd_down(args: argparse.Namespace) -> int:
    result = compose("down", "-v") if args.clean else compose("down")
    say(result.returncode == 0,
        "已經關掉，資料也刪了" if args.clean else "已經關掉 (Prometheus 與 Grafana 的資料留著) ")
    return result.returncode


# --------------------------------------------------------------------------- 進入點

def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Week 6 的 Grafana 環境 (Lab 06 與 Lab 07 兩個 case) ，一支程式跨三個作業系統")
    sub = parser.add_subparsers(dest="command")
    up = sub.add_parser("up", help="檢查、啟動、然後打開兩張儀表板 (不給子指令時的預設) ")
    up.add_argument("--no-browser", action="store_true", help="不要自動開瀏覽器")
    up.set_defaults(func=cmd_up)
    sub.add_parser("health", help="只檢查，不啟動").set_defaults(func=cmd_health)
    sub.add_parser("open", help="只開瀏覽器").set_defaults(func=cmd_open)
    logs = sub.add_parser("logs", help="看四個服務的紀錄")
    logs.add_argument("--tail", type=int, default=60)
    logs.set_defaults(func=cmd_logs)
    down = sub.add_parser("down", help="關掉")
    down.add_argument("--clean", action="store_true", help="順便刪掉 Prometheus 與 Grafana 的資料")
    down.set_defaults(func=cmd_down)

    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        args = parser.parse_args(["up", *(argv or [])])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
