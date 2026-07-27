# AIOps Anomaly Detection: Zero to Hero

這門課走一遍營運監控的完整資料流。OS 或網路設備產生 telemetry，exporter 曝露 `/metrics`，Prometheus scrape 並儲存時間序列，Grafana 顯示 dashboard。Python notebook 這一端讀整理好的 network telemetry CSV，做特徵工程、異常偵測與 RCA，結果再回到同一張 dashboard 上。

每個方法都要能解釋它為什麼被選、用什麼數字驗證，以及在真實系統裡該放在哪一層。不需要雲端帳號，Grafana Cloud 是選用延伸。

## 開始使用

環境還沒設定，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始，它給的是順序與每一步的驗收條件。

已經有自己的環境，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)，它會檢查 repo 路徑、Python 環境、Prometheus、Grafana Local 與 node_exporter。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師；想把時間序列資料轉成偵測流程的資料工程師；需要教學版範例資料而不是 production deployment template 的讀者。

不預設有 Kubernetes、雲端平台、Python package 開發或深度學習經驗。

## 學習成果

1. 啟動本機 Prometheus、Grafana Local 與 node_exporter，並確認資料真的被抓取。
2. 用 PromQL 查詢 counter、rate、label filtering 與 aggregation。
3. 從 raw network counters 建立可解釋的 time-series features，並比較四種 baseline。
4. 把偏離量收斂成 score、設門檻得到 label、加上 policy 成為 alert，並用 event recall、detection delay 與 alerts per day 評估這組設定。
5. 為 RCA 建立結構化 context，區分證據、假說與可執行行動。
6. 說明 Python 分析結果如何回到 Prometheus 與 Grafana 的 workflow。

## 教材路線

```text
getting-started -> observability stack 與 PromQL -> feature engineering
  -> anomaly detection 與 alerting -> RCA capstone
```

Python 主要讀取整理好的 CSV，不直接以 PromQL 作為演算法輸入。Notebook 把結果寫成 `outputs/workshop/*.csv` 與 `*.png`，用 `python -m http.server` 開啟資料夾，Grafana 端以 Infinity datasource 讀檔案。這條路徑沒有 exporter，寫檔用的就是 `to_csv()` 與 `savefig()`。

## Labs

位置：`labs/workshop/`，入口是 [`labs/workshop/README.md`](labs/workshop/README.md)。

這條路線是 GUI-first 的，換 port、拖時間軸、改 alert rule 都在 Grafana 上做。Notebook 這一端用 matplotlib 把每一段的結果畫出來。兩邊各自獨立，讀的是同一批數字，所以兩張圖對不起來就代表中間那條資料路徑斷了。

Grafana 端全部走官方功能。Datasource 用內建的檔案 provisioning（`infra/grafana/provisioning/datasources.yaml`），dashboard 用 UI 的 Import 匯入 `infra/grafana/dashboards/aiops-workshop.json`，告警規則寫在 `infra/prometheus/alerts.yml`，打在 `node_exporter` 的即時指標上，隨時可以用一次下載讓它響。

| Lab | 主題 | 建議時間 |
| --- | --- | --- |
| `00_observability_stack_and_promql.ipynb` | 兩條資料路徑與 PromQL。node_exporter 走 Prometheus，分析結果走檔案，故意弄壞再從 dashboard 讀出斷在哪一段 | 45–60 分鐘 |
| `01_network_traffic_feature_engineering.ipynb` | 單位契約、資料剖面、四種 baseline（rolling mean、median 與 MAD、seasonal、peer group）與 shape features | 60–75 分鐘 |
| `02_anomaly_detection_and_alerting.ipynb` | score 收成 label、label 通過 policy 成為 alert，以 event recall、detection delay 與 alerts per day 評估 | 60–75 分鐘 |
| `08_agentic_ai_rca_capstone.ipynb` | RCA context、agentic loop、human approval gate | 45–60 分鐘 |

另有 `toy_health_indicators_and_phm.ipynb`，二十分鐘的獨立走查，把多變量偏離收成有界的健康指標再談外推。

## 資料流

```text
actual OS / network telemetry
  -> exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> Grafana shows the operational dashboard

organized network telemetry CSV
  -> Python notebooks consume CSV
  -> outputs/workshop/*.csv and *.png
  -> python -m http.server serves that folder
  -> Grafana reads the files with the Infinity datasource
```

本課程的 synthetic CSV 對應的是「organized network telemetry CSV」這一層，模擬真實營運資料整理過後的樣子：欄位清楚、時間戳一致、可供 Python 分析。每份 notebook 讀取前一步的輸出，並把新的中間結果寫回 `outputs/workshop/`（gitignored）。中途失敗時，從失敗 notebook 的前一個 lab 重新執行，不要直接跳到後面的 lab。

## 設計地圖

notebook 裡的每個參數，都可以回到這張表找它在真實系統中的位置。

| Lab | 實務問題 | 主要設計決策 | 生產環境位置 |
| --- | --- | --- | --- |
| 00 Observability | 指標是否真的被收集，且可查詢 | scrape interval、label 設計、counter 與 rate、資料來源健康檢查 | Prometheus scrape config、Grafana dashboard |
| 01 Feature engineering | raw counters 如何變成可比較的訊號 | rate、ratio、rolling window、lag、多解析度 | Prometheus recording rules 或 feature service |
| 02 Detection 與 alerting | 哪些偏離值得告警，代價是多少 | 閾值、baseline 視窗、deadband、duration、誤報預算 | Prometheus alert rules、Alertmanager |
| 08 RCA | 如何把事件轉成可驗證的根因假說 | context window、evidence schema、LLM output contract、human gate | RCA webhook、ticket enrichment |

## 每章自我檢核

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | `00-check-your-setup.ipynb` 四格是否全部通過 |
| Observability | Prometheus 的 `up` 是否看得到 node_exporter |
| Feature engineering | `features.csv` 是否產生，欄位是否能追溯到 raw counters |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋 |
| Alerting | alert 是否被合理聚合，是否犧牲了需要立即處理的訊號 |
| RCA | RCA output 是否區分 evidence、hypothesis、recommended action |
| Deployment | Grafana dashboard、Prometheus rules 與 notebook 輸出是否對得起來 |

## 驗證指令

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口，可避免 command-line script 與 notebook kernel 使用不同 Python 環境而造成誤判。

Prometheus 設定用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

`alerts.yml` 的 recording 與 alert rules 打在 `node_exporter` 上，所以在自己的機器上就驗得起來。下載一個大檔案，`TrafficSurge` 會從 Normal 走到 Pending 再到 Firing。

## Repository 結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南
│   └── workshop/              # 工作坊 notebooks
├── data/
│   ├── synthetic/             # 可重建的 organized network telemetry CSV
│   └── sample/                # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/
│   └── workshop/              # Labs 產出（gitignored）
└── infra/
    ├── prometheus/            # Prometheus 設定與 node_exporter 上的 recording / alert rules
    └── grafana/
        ├── provisioning/      # datasource 的 YAML，用 Grafana 內建的 file provisioning
        └── dashboards/        # dashboard JSON，從 Grafana UI 匯入
```

工作坊 notebook 是自足的，載入、baseline、偵測、評估的函式就寫在每一份 notebook 開頭的 toolkit cell 裡，可以讀、可以改，不必先理解另一個函式庫。

## License

[MIT](LICENSE)
