"""偵測服務。讀 Prometheus、算分數、把分數曝露成 /metrics 讓 Prometheus 抓回去。

這支程式是整條線的第三個環節，也是這門課唯一自己寫的服務。每一輪只做三件事，
向 Prometheus 查一次網卡的接收速率，拿最近一段視窗算出偏離分數，再把速率與分數
寫進 Gauge，曝露的工作由 `start_http_server` 負責。

Prometheus 抓它的方式跟抓 node_exporter 一樣，所以 `aiops_traffic_score` 在 Grafana
與告警規則裡的用法，跟 `node_network_receive_bytes_total` 沒有分別。

    python detector.py

啟動之後，<http://localhost:9200/metrics> 會列出 aiops_traffic_score。

Lab 00 之後的每一節動的都是 `rolling_zscore()` 這一個函式。Lab 01 換掉它的基線，Lab 02
在它外面包門檻與政策。其餘的程式碼從頭到尾都不會再改。
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
traffic_score = Gauge("aiops_traffic_score", "Deviation of the receive rate from its rolling baseline",
                      ["device", "detector"])
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

    視窗裝不滿就先 return 0，因為兩三個樣本算出來的標準差小到沒有意義，隨便一點變動都會得到
    十幾二十的分數，門檻 3 會被這種數字灌爆。基線要暖機，這一行就是暖機期。
    """
    if len(window) < MIN_SAMPLES:
        return 0.0  # fewer samples than MIN_SAMPLES: population stdev would be unstable, skip scoring
    mean = sum(window) / len(window)  # center: arithmetic mean over the window
    stdev = (sum((x - mean) ** 2 for x in window) / len(window)) ** 0.5  # scale: population standard deviation (divide by n, not n-1)
    return (value - mean) / stdev if stdev > 0 else 0.0  # standardized deviation (value - mean) / stdev; 0 when stdev is zero, avoids division by zero


def your_detector(window, value):
    """空位，放你自己的偵測邏輯。介面跟 `rolling_zscore()` 一致，才能跟它並存，不必互相取代。

    輸入
        `window` — `value` 進來之前的滾動視窗，`deque(maxlen=WINDOW)`，暖機期沒裝滿。
        `value`  — 這一輪新量到的值，還沒被放進 `window`。
    輸出
        一個 float 分數，意義自訂，只要能配合下面的告警門檻。

    掛回 Prometheus：實作完把下面 `DETECTORS` 那一行的註解打開，不用碰 `main()`。多開的是
    `aiops_traffic_score{detector="your_detector"}` 這一組系列，跟 `rolling_zscore` 並存，不會
    蓋掉它。Prometheus 照原本的 scrape 設定抓回去；Grafana 要疊圖比較還是分開看自己決定。
    """
    raise NotImplementedError("在這裡放你的偵測邏輯，介面見上面的 docstring")


# 一次可以掛好幾個偵測器，各自獨立算、獨立曝露。新增一個就在這裡多加一行：介面跟
# rolling_zscore()/your_detector() 一樣，(window, value) -> float。key 是這個偵測器在
# Prometheus 裡的名字，寫進 aiops_traffic_score 的 detector label。
#
# alerts.yml 的 TrafficAnomaly 查的是裸的 aiops_traffic_score，不分 detector，所以每多開一個
# 偵測器，越線時就多一組告警實例，光看 device 分不出是哪一個觸發的。只想看某一個偵測器，查詢
# 或告警規則自己加 {detector="..."} 篩選。
DETECTORS = {
    "rolling_zscore": rolling_zscore,
    # "your_detector": your_detector,   # 實作好之後打開這一行
}


def main():
    metric, label, device = pick_target()
    start_http_server(EXPORT_PORT)
    print(f"detector 監看 {device}（{metric}），偵測器 {', '.join(DETECTORS)}，"
          f"每 {POLL_SECONDS} 秒查一次，曝露在 http://localhost:{EXPORT_PORT}/metrics\n"
          f"前 {MIN_SAMPLES * POLL_SECONDS} 秒是暖機期，分數固定是 0", flush=True)

    window = deque(maxlen=WINDOW)
    while True:
        rate = receive_rate(metric, label, device)
        if rate is not None:
            # 分數用「這個值進視窗之前」的視窗算，否則異常值會自己抬高自己的 baseline。
            # 每個偵測器獨立算、獨立失敗：還沒實作完的那個只印訊息，不會拖垮其他偵測器的分數。
            for name, detect in DETECTORS.items():
                try:
                    score = detect(window, rate)
                except Exception as exc:
                    print(f"detector {name} 失敗：{exc}", flush=True)
                    continue
                traffic_score.labels(device, name).set(score)
            traffic_bps.labels(device).set(rate)
            window.append(rate)
            window_fill.labels(device).set(len(window))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
