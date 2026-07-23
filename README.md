# AIOps Anomaly Detection: Zero to Hero

本課程幫助工程師建立可直接落地的 AIOps 實戰能力。課程從真實營運監控的資料流開始：OS 或網路設備產生 telemetry，exporter 暴露 `/metrics`，Prometheus scrape 並儲存時間序列，Grafana 顯示 operational dashboard。Python notebooks 則讀取整理好的 network telemetry CSV，設計特徵工程、異常偵測、告警降噪、預測與 RCA，再把數值結果輸出回 Prometheus / Grafana workflow。課程著重「可解釋、可驗證、可落地」的方法選擇，幫助工程師完成課程後即能在自己的監控系統中應用所學框架。

不需要雲端帳號。完成後可選擇延伸至 Grafana Cloud（選用）。

---

## 開始使用

**需要設定環境：** → [`labs/getting-started/`](labs/getting-started/README.md) — 先用 README 判斷起點；已有環境就開 setup check notebook，沒有環境就依 OS 連到對應安裝指南。

**已有自己的環境：** → [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb) — 直接用 notebook 檢查 kernel、Python packages、course exporter、Prometheus、Grafana Local 與 OS exporter 狀態。

---

## 適合對象

- 已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana Local 的維運或後端工程師。
- 想把時間序列資料轉成 AIOps 偵測流程的資料或維運工程師。
- 需要教學版範例資料，而不是只想看 production deployment template 的讀者。

不預設有 Kubernetes、雲端平台、Python package 開發或深度學習經驗。

---

## 學習成果

完成課程後，工程師應該能做到：

1. 啟動本機 Prometheus、Grafana Local 與 exporter，並確認資料真的被抓取。
2. 用 PromQL 查詢 counter、rate、label filtering 與 aggregation。
3. 從 raw network counters 建立可解釋的 time-series features。
4. 比較固定閾值、Z-score、SPC、Isolation Forest 與 forecasting 的適用情境。
5. 把低階 anomaly flags 聚合成較少、較可處理的 alerts。
6. 為 RCA 建立結構化 context，並區分證據、假說與可執行行動。
7. 說明 Python 分析結果如何回到 Prometheus / Grafana / alerting workflow。

---

## 教材路線

```text
getting-started
  -> observability stack
  -> PromQL
  -> feature engineering
  -> anomaly detection
  -> alert reduction
  -> forecasting
  -> RCA
  -> deployment checks
```

Python 主要讀取整理好的 CSV，不直接以 PromQL 作為演算法輸入。結果送到 Grafana 的方式兩條路線不同。

工作坊路線把結果寫成 `outputs/workshop/*.csv` 與 `*.png`，用 `python -m http.server` 開出資料夾，
Grafana 端以 Infinity datasource 讀檔案。這條路徑沒有 exporter，寫檔用的就是 `to_csv()` 與 `savefig()`。

自學路線把結果複製到 `outputs/prometheus-dropzone/current_results.csv`，由 `python_results_exporter`
曝露成 metrics，Prometheus scrape 之後在 Grafana 顯示。它示範的是 pull 模型的完整形狀，流程見
[`labs/getting-started/05-prometheus-dropzone.md`](labs/getting-started/05-prometheus-dropzone.md)。

### 路線 A：工作坊短版

位置：`labs/workshop/`，入口是 [`labs/workshop/README.md`](labs/workshop/README.md)。

這條路線是 GUI-first 的：換 port、拖時間軸、改 alert rule 都在 Grafana 上做。
Notebook 這一端用 matplotlib 把每一段的結果畫出來，和 self-study 那十份 notebook 同一套寫法。
兩邊各自獨立，讀的是同一批數字，所以兩張圖對不起來就代表中間那條資料路徑斷了。

Grafana 端全部走官方功能，這門課沒有為它寫過腳本。Datasource 用內建的檔案 provisioning
（`infra/grafana/provisioning/datasources.yaml`），dashboard 用 UI 的 Import 匯入
`infra/grafana/dashboards/aiops-workshop.json`，告警規則寫在 `infra/prometheus/alerts.yml`，
打在 `node_exporter` 的即時指標上，隨時可以用一次下載讓它響。

| Lab | 主題 | 建議時間 |
| --- | --- | --- |
| `00_observability_stack_and_promql.ipynb` | 兩條資料路徑與 PromQL。node_exporter 走 Prometheus，分析結果走檔案，故意弄壞再從 dashboard 讀出斷在哪一段 | 45–60 分鐘 |
| `01_network_traffic_feature_engineering.ipynb` | 單位契約、資料剖面、四種 baseline（rolling mean、median 與 MAD、seasonal、peer group）與 shape features | 60–75 分鐘 |
| `02_anomaly_detection_and_alerting.ipynb` | score 收成 label、label 通過 policy 成為 alert，以 event recall、detection delay 與 alerts per day 評估 | 60–75 分鐘 |
| `08_agentic_ai_rca_capstone.ipynb` | RCA context、agentic loop、human approval gate | 45–60 分鐘 |

### 路線 B：完整自學版

位置：`labs/self-study/`

主要使用 repository 內建 synthetic data。它不是另一條 production 架構，而是用可重建 CSV 模擬真實網路 telemetry 已被整理後的形態，讓 Python 演算法練習可以穩定重跑、容易定位錯誤。

1. `data/synthetic/simulator_rrd_metrics.ipynb`
2. `labs/self-study/00_observability_stack.ipynb`
3. `labs/self-study/01_time_series_features.ipynb`
4. `labs/self-study/02_baseline_anomaly_detection.ipynb`
5. `labs/self-study/03_spc_anomaly_detection.ipynb`
6. `labs/self-study/04_ml_anomaly_detection.ipynb`
7. `labs/self-study/05_alert_reduction.ipynb`
8. `labs/self-study/06_forecasting.ipynb`
9. `labs/self-study/07_root_cause_analysis.ipynb`
10. `labs/self-study/08_deploy_to_production.ipynb`

---

## 資料流

```text
actual OS / network telemetry
  -> exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> Grafana shows the operational dashboard

organized network telemetry CSV
  -> Python notebooks consume CSV
  -> outputs/self-study/*.csv or outputs/workshop/*.csv
  -> optional copy to outputs/prometheus-dropzone/current_results.csv
  -> python_results_exporter exposes Python results as /metrics
  -> Prometheus scrapes aiops_python_result
  -> Grafana shows Python anomaly / forecast / RCA signals
```

本課程的 synthetic CSV 對應的是「organized network telemetry CSV」這一層。它模擬真實營運資料被整理成欄位清楚、時間戳一致、可供 Python 分析的格式。每個 self-study notebook 會讀取前一步輸出，並把新的中間結果寫回 `outputs/self-study/`（gitignored）。中途失敗時，從失敗 notebook 的前一個 lab 重跑，不要直接跳到後面的 lab。

---

## 演算法與架構設計地圖

| 階段 | 實務問題 | 主要設計決策 | 生產環境位置 |
| --- | --- | --- | --- |
| Lab 00 Observability | 指標是否真的被收集，且可查詢？ | scrape interval、label 設計、counter 與 rate、資料來源健康檢查 | Prometheus scrape config、Grafana Local / Grafana Cloud dashboard |
| Lab 01 Feature engineering | raw counters 如何變成可比較的訊號？ | rate、ratio、rolling window、lag、多解析度 | Prometheus recording rules 或 feature service |
| Lab 02 Baseline detection | 哪些偏離值得告警？ | 閾值、baseline 視窗、deadband、誤報預算 | Prometheus alert rules、Grafana Cloud annotations |
| Lab 03 SPC | 如何區分隨機波動與製程偏移？ | control limits、EWMA 記憶長度、CUSUM 靈敏度 | rule service 或 batch validation |
| Lab 04 ML anomaly detection | 單一指標看不出來的組合異常如何處理？ | feature set、contamination、解釋方式、重訓頻率 | scoring service，必要時回寫 Prometheus |
| Lab 05 Alert reduction | 如何把大量 flags 變成可處理事件？ | grouping window、problem taxonomy、suppression rule | Alertmanager、event correlation service |
| Lab 06 Forecasting | 能否在 SLA 受影響前提早預警？ | horizon、prediction interval、季節性假設 | forecasting service、capacity planning dashboard |
| Lab 07 RCA | 如何把事件轉成可驗證的根因假說？ | context window、evidence schema、LLM output contract | RCA webhook、ticket enrichment |
| Lab 08 Deployment | 探索邏輯如何進入 24/7 監控？ | 哪些放在 Prometheus rules，哪些放在 Python service，哪些先用 CSV 驗證，哪裡保留 human gate | production monitoring pipeline |

這張表是全課的設計骨架。notebook 中的每個參數，都可以回到這張表找它在系統中的位置。

---

## 每章自我檢核

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | `00-check-your-setup.ipynb` 是否通過 Python kernel / packages、course exporter、Prometheus 與 Grafana Local 檢查？ |
| Observability | Prometheus 的 `up` 是否能看到 exporter 與 OS exporter？ |
| Feature engineering | `features.csv` 是否產生？欄位是否能追溯到 raw counters？ |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋？ |
| Alert reduction | raw alerts 是否被合理聚合？是否犧牲了需要立即處理的訊號？ |
| Forecasting | prediction interval 是否太窄或太寬？ |
| RCA | RCA output 是否區分 evidence、hypothesis、recommended action？ |
| Deployment | Grafana Local dashboard、Prometheus rules 與 notebook 輸出是否對得起來？ |

---

## 驗證指令

互動式檢查請開啟：

```text
labs/getting-started/00-check-your-setup.ipynb
```

若要確認本機是否已就緒，請直接執行 setup check notebook。這是唯一建議的檢查入口，可避免 command-line script 與 notebook kernel 使用不同 Python 環境而造成誤判。

Prometheus 設定可用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
promtool check config infra/prometheus/prometheus.linux.yml
promtool check config infra/prometheus/prometheus.windows.yml
```

`alerts.yml` 的 recording 與 alert rules 打在 `node_exporter` 上，所以在自己的機器上就驗得起來：
下載一個大檔案，`TrafficSurge` 會從 Normal 走到 Pending 再到 Firing。

---

## Repository 結構

```text
.
├── README.md                    # 本文件
├── environment.yml              # conda 課程環境
├── labs/
│   ├── getting-started/         # setup 主入口、互動式檢查 notebook、各平台安裝指南
│   ├── workshop/                # 工作坊短版 notebooks
│   └── self-study/              # 完整自學版 notebooks
├── data/
│   ├── synthetic/               # 可重建的 organized network telemetry CSV
│   └── sample/                  # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/                     # Labs 產出（gitignored）
│   ├── workshop/
│   ├── self-study/
│   └── prometheus-dropzone/      # current_results.csv feeds python_results_exporter
├── diagram/                     # 圖表唯一來源（.drawio），labs 下的 .svg 由 build 產生
├── infra/
│   ├── prometheus/              # Prometheus 設定與 node_exporter 上的 recording / alert rules
│   ├── grafana/
│   │   ├── provisioning/        # datasource 的 YAML，用 Grafana 內建的 file provisioning
│   │   └── dashboards/          # dashboard JSON，從 Grafana UI 匯入
│   ├── aiopskit/                # 工作坊分析函式庫：載入、baseline、偵測、評估
│   ├── build_diagrams.py        # diagram/*.drawio -> labs/*/diagrams/*.svg
│   ├── svg_flatten.py           # build 的第二段，把 draw.io 的雙份標籤攤平成原生 text
│   ├── rrd_exporter.py          # 自學版：organized telemetry CSV to Prometheus metrics
│   └── python_results_exporter.py # 自學版：Python result CSV to Prometheus metrics
└── tests/                       # aiopskit 迴歸測試
```

圖表改動走 `diagram/*.drawio`，改完跑 `python infra/build_diagrams.py`。
`labs/*/diagrams/*.svg` 是產生物，手改會在下一次 build 被蓋掉，細節見
[`diagram/README.md`](diagram/README.md)。

---

## License

[MIT](LICENSE)
