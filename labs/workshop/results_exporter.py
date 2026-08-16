"""重播服務。讀 notebook 算完寫出的 CSV，把裡面的數值欄位曝露成 /metrics 讓 Prometheus 抓。

這支程式是 Week 6 專用的，跟 `detector.py` 是姊妹檔，差別只在分數從哪裡來。

`detector.py` 是正式環境的形狀，模型跑在服務裡，每一輪自己算出當下的分數。Lab 06 的
Prophet 與 Lab 07 的 hybrid 排名都需要一整段歷史才配適得起來，在課堂上跑不成長駐服務，
所以改成 notebook 算完寫 CSV、這支程式把 CSV 重播成 metrics。

換句話說，兩支程式接的是同一條線的同一個位置:

    detector.py       Prometheus -> 算分數 -> /metrics -> Prometheus
    results_exporter  notebook CSV -> 重播 -> /metrics -> Prometheus

從 Prometheus 往後看完全一樣，所以 Grafana 的 panel 與 alerts 規則寫法沒有分別。這件事
就是 Lab 06 那一節「教學版 vs 正式環境」要講的重點。

    RESULTS_CSV_PATH=outputs/workshop/forecast_results.csv \
    RESULT_COLUMNS=traffic_total,y_hat,forecast_30m,early_warning_30m,forecast_risk_score,resid_z \
    python labs/workshop/results_exporter.py

啟動之後，<http://localhost:8010/metrics> 會列出 aiops_python_result。

CSV 換掉不用重啟，這支程式看 mtime，檔案一變就重新載入。
"""
import os
import time
from pathlib import Path

import pandas as pd
from prometheus_client import Gauge, start_http_server

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "outputs" / "workshop" / "forecast_results.csv"

CSV_PATH = Path(os.environ.get("RESULTS_CSV_PATH", DEFAULT_CSV))
if not CSV_PATH.is_absolute():
    CSV_PATH = REPO_ROOT / CSV_PATH

EXPORT_PORT = int(os.environ.get("RESULTS_EXPORTER_PORT", 8010))
POLL_SECONDS = 5

# 重播倍速。預設 3600 是「一秒等於一小時」，一份七天的 CSV 大約三分鐘跑完一輪，
# panel 會像值班畫面一樣往前走。設成 1 就是照真實時間重播。
REPLAY_SPEED_X = float(os.environ.get("REPLAY_SPEED_X", 3600))

# 要曝露哪些數值欄位。沒有指定就用下面這張偏好清單跟 CSV 取交集，再沒有就退回全部數值欄位。
CONFIGURED_COLUMNS = [c.strip() for c in os.environ.get("RESULT_COLUMNS", "").split(",") if c.strip()]
PREFERRED_COLUMNS = [
    "traffic_total", "y_hat", "y_hat_lower", "y_hat_upper",
    "forecast_30m", "early_warning_30m", "forecast_risk_score", "resid_z", "p_exceed",
    "root_cause_score", "confidence_score", "escalation_flag", "hit_at_3",
    "cross_port_synchrony", "z_traffic_total", "z_error_rate", "z_discard_rate", "z_broadcast_total",
]

# 這幾欄變成 Prometheus 的 label，不是數值。CSV 沒有的欄位會補空字串。
LABEL_COLUMNS = [c.strip() for c in os.environ.get(
    "RESULT_LABEL_COLUMNS", "device_id,port_id,port_role,event_label,ml_method").split(",") if c.strip()]

result_value = Gauge("aiops_python_result", "Notebook result replayed for Prometheus",
                     ["source", "column", *LABEL_COLUMNS])
result_clock = Gauge("aiops_python_result_timestamp", "Simulated timestamp the replay is currently at")


def pick_columns(frame):
    """挑出要曝露的數值欄位。指定的欄位少一個就直接停，不要安靜地少畫一條線。"""
    if CONFIGURED_COLUMNS:
        missing = [c for c in CONFIGURED_COLUMNS if c not in frame.columns]
        if missing:
            raise SystemExit(f"{CSV_PATH} 沒有 RESULT_COLUMNS 指定的欄位: {missing}")
        return CONFIGURED_COLUMNS
    preferred = [c for c in PREFERRED_COLUMNS if c in frame.columns]
    if preferred:
        return preferred
    numeric = [c for c in frame.select_dtypes(include="number").columns
               if c not in {"timestamp", *LABEL_COLUMNS}]
    if not numeric:
        raise SystemExit(f"{CSV_PATH} 沒有任何數值欄位可以曝露，請用 RESULT_COLUMNS 指定")
    return numeric[:8]


def load_results(path):
    if not path.exists():
        return pd.DataFrame(), []
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise SystemExit(f"{path} 必須有 timestamp 欄位，重播的時間軸靠它")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.sort_values("timestamp").reset_index(drop=True), pick_columns(frame)


class Replay:
    """CSV 目前的內容、重播進度，以及「檔案換了要重讀」這件事。"""

    def __init__(self, path):
        self.path = path
        self.frame, self.columns = load_results(path)
        self.mtime = path.stat().st_mtime if path.exists() else None
        self.wall_start = time.time()

    def reload_if_changed(self):
        if not self.path.exists():
            if self.mtime is not None:
                self.frame, self.columns, self.mtime = pd.DataFrame(), [], None
                result_value.clear()
                print(f"等待 {self.path} 出現", flush=True)
            return
        mtime = self.path.stat().st_mtime
        if mtime == self.mtime:
            return
        self.frame, self.columns = load_results(self.path)
        self.mtime = mtime
        self.wall_start = time.time()
        # 換 CSV 的時候要清掉舊的 series，否則上一份的欄位會一直停在最後一個值不動。
        result_value.clear()
        print(f"重新載入 {self.path}，欄位: {', '.join(self.columns)}", flush=True)

    def now(self):
        """重播走到 CSV 時間軸的哪一點。走完就從頭再來一輪。"""
        if self.frame.empty:
            return None
        start, end = self.frame["timestamp"].min(), self.frame["timestamp"].max()
        elapsed = (time.time() - self.wall_start) * REPLAY_SPEED_X
        t = start + pd.Timedelta(seconds=elapsed)
        span = end - start
        return start + (t - start) % span if t > end and span.total_seconds() > 0 else min(t, end)

    def rows_at(self, t):
        """這個時間點該曝露哪幾列: 時間軸上最後一批不晚於 t 的列(每個 port 各一列)。"""
        before = self.frame[self.frame["timestamp"] <= t]
        return before[before["timestamp"] == before["timestamp"].max()] if len(before) else self.frame.head(0)


def main():
    replay = Replay(CSV_PATH)
    start_http_server(EXPORT_PORT)
    print(f"重播 {CSV_PATH}，{REPLAY_SPEED_X:g} 倍速，曝露在 http://localhost:{EXPORT_PORT}/metrics")
    print(f"數值欄位: {', '.join(replay.columns) if replay.columns else '(還沒有 CSV)'}")
    print(f"label 欄位: {', '.join(LABEL_COLUMNS)}", flush=True)

    while True:
        replay.reload_if_changed()
        t = replay.now()
        if t is not None:
            result_clock.set(t.timestamp())
            for _, row in replay.rows_at(t).iterrows():
                labels = ["" if pd.isna(row.get(c, "")) else str(row.get(c, "")) for c in LABEL_COLUMNS]
                for col in replay.columns:
                    if not pd.isna(row[col]):
                        result_value.labels(CSV_PATH.name, col, *labels).set(float(row[col]))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
