# AIOps Anomaly Detection: Zero to Hero

本課程幫助工程師建立可直接落地的 AIOps 實戰能力。透過本機 Prometheus、Grafana Local 與課程 exporter，學員完整走過特徵工程、異常偵測、告警降噪、預測與根因分析，並理解每個判斷在真實值班環境中的位置與限制。課程著重「可解釋、可驗證、可落地」的方法選擇，幫助工程師完成課程後即能在自己的監控系統中應用所學框架。

不需要雲端帳號。完成後可選擇延伸至 Grafana Cloud（選用）。

---

## 開始使用

**需要設定環境：** → [`labs/getting-started/`](labs/getting-started/README.md) — 環境設定步驟、路徑選擇、就緒確認，全部在這裡。

**已有自己的環境：** → [`labs/getting-started/05-readiness-check.md`](labs/getting-started/05-readiness-check.md) — 直接確認 Python 套件、Prometheus、Grafana Local 是否符合課程需求。

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
7. 說明模型輸出如何回到 Prometheus / Grafana / alerting workflow。

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

### 路線 A：工作坊短版

位置：`labs/workshop/`

使用 Prometheus 查詢即時本機指標，讓工程師先看到自己的機器產生 metrics，再進入特徵工程、異常偵測與 RCA capstone。

| Lab | 主題 | 建議時間 |
| --- | --- | --- |
| `00_observability_stack_and_promql.ipynb` | Prometheus、node_exporter、PromQL | 45–60 分鐘 |
| `01_network_traffic_feature_engineering.ipynb` | EDA、rate、rolling、lag、多解析度 features | 60–75 分鐘 |
| `02_anomaly_detection_and_alerting.ipynb` | 固定閾值、Z-score、deadband、change point | 60–75 分鐘 |
| `08_agentic_ai_rca_capstone.ipynb` | RCA context、agentic loop、human approval gate | 45–60 分鐘 |

### 路線 B：完整自學版

位置：`labs/self-study/`

主要使用 repository 內建 synthetic data，輸出可重建，錯誤比較容易定位。

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
data/synthetic/synthetic_rrd_metrics.csv
  -> outputs/self-study/features.csv
  -> outputs/self-study/baseline_anomaly_flags.csv
  -> outputs/self-study/spc_results.csv
  -> outputs/self-study/ml_anomaly_scores.csv
  -> outputs/self-study/raw_alerts.csv
  -> outputs/self-study/reduced_alerts.csv
  -> outputs/self-study/forecast_results.csv
```

每個 self-study notebook 會讀取前一步輸出，並把新的中間結果寫回 `outputs/self-study/`（gitignored）。中途失敗時，從失敗 notebook 的前一個 lab 重跑，不要直接跳到後面的 lab。

---

## 演算法與架構設計地圖

| 階段 | 實務問題 | 主要設計決策 | 生產環境位置 |
| --- | --- | --- | --- |
| Lab 00 Observability | 指標是否真的被收集，且可查詢？ | scrape interval、label 設計、資料來源健康檢查 | Prometheus scrape config、Grafana Local / Grafana Cloud dashboard |
| Lab 01 Feature engineering | raw counters 如何變成可比較的訊號？ | rate、ratio、rolling window、lag、多解析度 | Prometheus recording rules 或 feature service |
| Lab 02 Baseline detection | 哪些偏離值得告警？ | 閾值、baseline 視窗、deadband、誤報預算 | Prometheus alert rules、Grafana Cloud annotations |
| Lab 03 SPC | 如何區分隨機波動與製程偏移？ | control limits、EWMA 記憶長度、CUSUM 靈敏度 | rule service 或 batch validation |
| Lab 04 ML anomaly detection | 單一指標看不出來的組合異常如何處理？ | feature set、contamination、解釋方式、重訓頻率 | scoring service，必要時回寫 Prometheus |
| Lab 05 Alert reduction | 如何把大量 flags 變成可處理事件？ | grouping window、problem taxonomy、suppression rule | Alertmanager、event correlation service |
| Lab 06 Forecasting | 能否在 SLA 受影響前提早預警？ | horizon、prediction interval、季節性假設 | forecasting service、capacity planning dashboard |
| Lab 07 RCA | 如何把事件轉成可驗證的根因假說？ | context window、evidence schema、LLM output contract | RCA webhook、ticket enrichment |
| Lab 08 Deployment | 探索邏輯如何進入 24/7 監控？ | 哪些放在 Prometheus，哪些放在 Python service，哪裡保留 human gate | production monitoring pipeline |

這張表是全課的設計骨架。notebook 中的每個參數，都可以回到這張表找它在系統中的位置。

---

## 每章自我檢核

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | conda 環境、notebook JSON、dashboard JSON 是否通過 `validate_setup.py`？ |
| Observability | Prometheus 的 `up` 是否能看到 exporter 與 OS exporter？ |
| Feature engineering | `features.csv` 是否產生？欄位是否能追溯到 raw counters？ |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋？ |
| Alert reduction | raw alerts 是否被合理聚合？是否犧牲了需要立即處理的訊號？ |
| Forecasting | prediction interval 是否太窄或太寬？ |
| RCA | RCA output 是否區分 evidence、hypothesis、recommended action？ |
| Deployment | Grafana Local dashboard、Prometheus rules 與 notebook 輸出是否對得起來？ |

---

## 驗證指令

從 repository 根目錄執行：

```bash
conda activate aiops-anomaly-zero-to-hero
python labs/getting-started/scripts/validate_setup.py
```

只想驗證 repository 結構、暫時跳過 Python 與服務檢查：

```bash
python labs/getting-started/scripts/validate_setup.py --repo-only
```

Prometheus 設定可用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
promtool check config infra/prometheus/prometheus.windows.yml
```

---

## Repository 結構

```text
.
├── README.md                    # 本文件
├── environment.yml              # conda 課程環境
├── labs/
│   ├── getting-started/         # 設定指南（01a–01c、02–04）與就緒確認（05）
│   ├── workshop/                # 工作坊短版 notebooks
│   └── self-study/              # 完整自學版 notebooks
├── data/
│   ├── synthetic/               # 可由 simulator 重建的 RRD-like metrics
│   └── sample/                  # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/                     # Labs 產出（gitignored）
│   ├── workshop/
│   └── self-study/
└── infra/
    ├── prometheus/              # Prometheus 設定（prometheus.macos.yml / prometheus.windows.yml）
    ├── grafana/                 # Dashboard JSON 與 datasource 設定
    └── rrd_exporter.py          # CSV-to-Prometheus metrics exporter (self-study)
```

---

## License

[MIT](LICENSE)
