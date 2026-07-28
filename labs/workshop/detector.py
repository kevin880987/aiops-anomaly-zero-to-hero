"""偵測服務：讀 Prometheus、算分數、把分數曝露成 /metrics 讓 Prometheus 抓回去。

這支程式是整條線的第三個環節，也是這門課唯一自己寫的服務。它做的事只有三件：

    1. 對 Prometheus 查一次網卡的接收速率
    2. 拿最近一段視窗算一個偏離分數
    3. 把速率與分數寫進 Gauge，`start_http_server` 負責曝露在 /metrics

Prometheus 抓它的方式跟抓 node_exporter 完全一樣，所以 `aiops_traffic_score` 在
Grafana 與告警規則裡的用法，跟 `node_network_receive_bytes_total` 沒有分別。

    python detector.py

跑起來之後 <http://localhost:9200/metrics> 看得到 aiops_traffic_score。

`rolling_zscore()` 是這門課接下來要動的那一個函式。Lab 01 換掉它的 baseline，
Lab 02 在它外面包門檻與政策。其餘的程式碼在後面兩節都不會再改。
"""
import os
import time
from collections import deque

import requests
from prometheus_client import Gauge, start_http_server

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
EXPORT_PORT = int(os.environ.get("EXPORT_PORT", 9200))
POLL_SECONDS = 15
WINDOW = 40           # 40 個樣本、15 秒一次，大約 10 分鐘的滾動視窗
MIN_SAMPLES = 10      # 視窗裝到這個數量之前不評分，理由見 rolling_zscore()

# node_exporter 與 windows_exporter 量的是同一件事，名字不一樣，網卡的 label 也不一樣。
# 啟動的時候兩個都問一次，哪一個回得出資料就用哪一個。
EXPORTERS = [
    ("node_network_receive_bytes_total", "device"),
    ("windows_net_bytes_received_total", "nic"),
]

traffic_bps = Gauge("aiops_traffic_bps", "Interface receive rate this detector queried", ["device"])
traffic_score = Gauge("aiops_traffic_score", "Deviation of the receive rate from its rolling baseline", ["device"])
window_fill = Gauge("aiops_detector_window_samples", "Samples currently in the rolling window", ["device"])


def promql(query):
    """打 Prometheus 的 HTTP API。Grafana 在背後做的是同一件事。"""
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query",
                            params={"query": query}, timeout=5)
    response.raise_for_status()
    return response.json()["data"]["result"]


def pick_target():
    """選 exporter，再挑最近一分鐘接收量最大的那張網卡。

    虛擬介面很多，挑錯會得到一條平的零線，所以用 topk 讓資料自己指出哪一張在傳。
    """
    for metric, label in EXPORTERS:
        rows = promql(f"topk(1, rate({metric}[1m]))")
        if rows:
            return metric, label, rows[0]["metric"][label]
    raise SystemExit("Prometheus 查不到任何網卡指標，先確認 exporter 起來了、而且被抓到")


def receive_rate(metric, label, device):
    """這張網卡現在每秒收多少 bytes。counter 要先差分才有意義，rate() 做的就是差分。"""
    rows = promql(f'rate({metric}{{{label}="{device}"}}[1m])')
    return float(rows[0]["value"][1]) if rows else None


def rolling_zscore(window, value):
    """離平均幾個標準差。這是最素樸的一種偏離分數，Lab 01 會說明它什麼時候會騙人。

    視窗裝不滿就先回 0，因為兩三個樣本算出來的標準差小到沒有意義，隨便一點變動都會得到
    十幾二十的分數，門檻 3 會被這種數字灌爆。基線要暖機，這一行就是暖機期。
    """
    if len(window) < MIN_SAMPLES:
        return 0.0
    mean = sum(window) / len(window)
    stdev = (sum((x - mean) ** 2 for x in window) / len(window)) ** 0.5
    return (value - mean) / stdev if stdev > 0 else 0.0


def main():
    metric, label, device = pick_target()
    start_http_server(EXPORT_PORT)
    print(f"detector 監看 {device}（{metric}），每 {POLL_SECONDS} 秒查一次，"
          f"曝露在 http://localhost:{EXPORT_PORT}/metrics\n"
          f"前 {MIN_SAMPLES * POLL_SECONDS} 秒是暖機期，分數固定是 0", flush=True)

    window = deque(maxlen=WINDOW)
    while True:
        rate = receive_rate(metric, label, device)
        if rate is not None:
            # 分數用「這個值進視窗之前」的視窗算，否則異常值會自己抬高自己的 baseline。
            traffic_score.labels(device).set(rolling_zscore(window, rate))
            traffic_bps.labels(device).set(rate)
            window.append(rate)
            window_fill.labels(device).set(len(window))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
