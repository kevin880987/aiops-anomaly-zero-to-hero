# AIOps Anomaly Detection: Zero to Hero

這門課走一遍營運監控的完整資料流，而且是接得起來、跑得下去的那一種。OS 產生 telemetry，exporter 曝露 `/metrics`，Prometheus scrape 並儲存時間序列。接著課程自己寫的一支偵測服務回頭查 Prometheus、算出偏離分數、把分數曝露成 `/metrics`，於是 Prometheus 把它當成一般指標抓回去，Grafana 與告警規則查詢的就是那個分數。

重點在演算法，不在畫面。Lab 00 一次把整條管線接完，之後兩節處理的是那個分數該怎麼算。

每個方法都要能解釋它為什麼被選、用什麼數字驗證，以及在真實系統裡該放在哪一層。不需要雲端帳號，Grafana Cloud 是選用延伸。

教材按課程進度釋出。這一份涵蓋環境設定與 Lab 00 到 Lab 02，也就是第一天要用到的全部內容；RCA capstone 與自學路線在後續梯次發布。

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
5. 把 Python 算出來的分數送回 Prometheus，讓 Grafana 與 alert rules 以查詢一般指標的方式取用它。

## 教材路線

```text
getting-started -> 把整條管線接起來 -> feature engineering -> anomaly detection 與 alerting
```

Lab 00 讀的是這台機器此刻的流量，走 Prometheus。Lab 01 與 Lab 02 讀 `data/synthetic/` 底下標好真值的歷史 CSV，因為演算法要拿有答案的資料才評得出好壞，那兩節全程用 matplotlib 畫圖。兩者的關係很直接：在歷史資料上挑出來的 baseline 與政策，就是要放進 Lab 00 那支服務裡的演算法。

## Labs

位置：`labs/workshop/`，入口是 [`labs/workshop/README.md`](labs/workshop/README.md)。

`labs/workshop/detector.py` 是這門課唯一自己寫的服務，六十行上下，讀得懂也改得動。它算分數的那個函式正是 Lab 01 與 Lab 02 要換掉的部分，其餘的程式碼在後面兩節都不會再動。

Grafana 端全部走官方功能，datasource 用內建的檔案 provisioning（`infra/grafana/provisioning/datasources.yaml`）接上 Prometheus。Dashboard 在 Lab 00 逐格建立，一張 panel 畫原始速率，一張畫算出來的分數，第三張畫告警現在的狀態，`infra/grafana/dashboards/aiops-workshop.json` 是建完之後核對用的答案卷。告警規則寫在 `infra/prometheus/alerts.yml`，隨時可以用一次下載讓它響。

| Lab | 主題 | 建議時間 |
| --- | --- | --- |
| `00_end_to_end_pipeline.ipynb` | 把整條管線接起來。counter 與 rate、Python 服務怎麼進到 Prometheus、`for:` 怎麼擋掉雜訊，再故意弄壞四次讀出斷在哪一段 | 45 到 60 分鐘 |
| `01_network_traffic_feature_engineering.ipynb` | 單位契約、資料剖面、四種 baseline（rolling mean、median 與 MAD、seasonal、peer group）與 shape features | 60 到 75 分鐘 |
| `02_anomaly_detection_and_alerting.ipynb` | score 收成 label、label 通過 policy 成為 alert，以 event recall、detection delay 與 alerts per day 評估 | 60 到 75 分鐘 |

## 資料流

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> detector.py queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

分數繞回 Prometheus 這一步是整個設計的關鍵。繞回去之後下游沒有一格知道它是 Python 算的，所以上線的時候換掉的是演算法，管線原封不動。

Lab 01 與 Lab 02 另外讀 `data/synthetic/` 底下的 synthetic CSV，那是真實營運資料整理過後的樣子：五個 port、一整個月、十八個標好的事件。有真值才量得出一個 baseline 好不好，這台機器此刻的流量沒有真值可比。

## 設計地圖

notebook 裡的每個參數，都可以回到這張表找它在真實系統中的位置。

| Lab | 實務問題 | 主要設計決策 | 生產環境位置 |
| --- | --- | --- | --- |
| 00 Pipeline | 指標是否真的被收集、算完的分數是否回得去 | scrape interval、label 設計、counter 與 rate、哪一段計算該放在 PromQL 哪一段放在服務裡 | Prometheus scrape config、偵測服務、Grafana dashboard |
| 01 Feature engineering | raw counters 如何變成可比較的訊號 | rate、ratio、rolling window、lag、多解析度 | Prometheus recording rules 或 feature service |
| 02 Detection 與 alerting | 哪些偏離值得告警，代價是多少 | 閾值、baseline 視窗、deadband、duration、誤報預算 | Prometheus alert rules、Alertmanager |

## 每章自我檢核

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | `00-check-your-setup.ipynb` 四格是否全部通過 |
| Observability | Prometheus 的 `up` 對 node_exporter 與 aiops-detector 兩個 job 是否都是 1 |
| Feature engineering | 算出來的欄位是否能一路追溯回 raw counters |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋 |
| Alerting | alert 是否被合理聚合，是否犧牲了需要立即處理的訊號 |
| Deployment | 換掉偵測服務裡的演算法之後，dashboard 與 alert rules 是否不用改也能跟著變 |

## 驗證指令

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口，可避免 command-line script 與 notebook kernel 使用不同 Python 環境而造成誤判。

Prometheus 設定用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

`alerts.yml` 的規則打在自己這台機器上，所以隨時驗得起來。下載一個大檔案，`TrafficAnomaly` 會從 Normal 走到 Pending 再到 Firing。

## Repository 結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南
│   └── workshop/              # 工作坊 notebooks、detector.py、diagrams/
├── data/
│   ├── synthetic/             # 可重建的 organized network telemetry CSV
│   └── sample/                # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/
│   └── workshop/              # Labs 產出（gitignored）
└── infra/
    ├── prometheus/            # 三個平台的 scrape 設定，以及 recording / alert rules
    └── grafana/
        ├── provisioning/      # datasource 的 YAML，用 Grafana 內建的 file provisioning
        └── dashboards/        # dashboard JSON，建完之後核對用的答案卷
```

工作坊 notebook 是自足的，載入、baseline、偵測、評估的函式就寫在每一份 notebook 開頭的 toolkit cell 裡，可以讀、可以改，不必先理解另一個函式庫。

## License

[MIT](LICENSE)
