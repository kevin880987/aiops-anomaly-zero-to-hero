# AIOps Anomaly Detection: Zero to Hero

這門課從網卡的 counter 開始，一路接到告警，中間每一段都在你自己的機器上執行。node_exporter 把作業系統的 telemetry 曝露成 `/metrics`，Prometheus 每 5 秒抓一次，存成時間序列。接著課程自己寫的一支偵測服務回頭查 Prometheus，算出偏離分數並取名 `aiops_traffic_score`，再把它曝露成 `/metrics`，於是 Prometheus 把它當成一般指標抓回去。Grafana 的 panel 與告警規則查詢的都是這個偏離分數。

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> the detector service queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

偏離分數繞回 Prometheus 之後，下游沒有任何一段知道它是 Python 算的。這個做法決定了整門課的形狀：改良演算法不必動 pipeline，所以課程的時間花在演算法上，畫面只用來確認演算法的輸出。

## 開始使用

還沒設定環境的讀者，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始。那份文件給的是安裝順序，以及每一步過關的條件。

已經有自己環境的讀者，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)。它逐格檢查教材根目錄、Python 環境、Prometheus、Grafana Local 與 node_exporter，任何一格失敗都會指出該補哪一份安裝指南。

課程教材放在 `labs/workshop/`，依課程進度分批發布，上到那幾節才會發到你手上。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師。想把時間序列資料轉成偵測流程的資料工程師。想要一份可以完整閱讀、也可以自行修改的教學版範例的讀者。

不預設你有 Kubernetes、雲端平台、Python package 開發或深度學習的經驗，也不需要任何雲端帳號。Grafana Cloud 是選用延伸。

課程的資料與設定都是為了教學而寫，直接搬進 production 並不合適。

## 教材結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── diagrams/                  # 課程圖表，各章共用同一份，來源在 materials/diagrams/
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南、screenshots/
│   └── workshop/              # 課程教材，依課程進度分批發布
├── data/
│   ├── synthetic/             # 可重建的 organized network telemetry CSV
│   └── sample/                # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/
│   └── workshop/              # 課程產出，不隨教材發布
└── infra/
    ├── prometheus/            # 三個平台的 scrape 設定，以及 recording / alert rules
    └── grafana/
        ├── provisioning/      # datasource 的 YAML，用 Grafana 內建的 file provisioning
        └── dashboards/        # 示範用的 dashboard JSON，匯入即可看到即時資料
```

課程用兩種資料。走 Prometheus 的那一種是這台機器此刻的流量，真實，但沒有真值可以對照。`data/synthetic/` 底下是標好真值的歷史 CSV，那是真實營運資料整理過後的樣子，有真值才量得出一個 baseline 好不好。

## 驗證

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口。在終端機另外執行檢查腳本會給出誤判，因為 command-line Python 與 notebook kernel 不一定是同一個環境。

Prometheus 的設定檔用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

## License

[MIT](LICENSE)
