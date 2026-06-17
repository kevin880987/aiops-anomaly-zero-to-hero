# 教材總覽

這份教材把 AIOps anomaly detection 拆成一條可執行的學習路徑。學員不是只看模型結果，而是從 telemetry 來源、Prometheus 查詢、特徵工程、偵測方法、告警降噪、預測與 RCA 一路走到營運判斷。

## 適合對象

- 第一次接觸 Prometheus / Grafana，但已能照著指令操作終端機的學員。
- 想把時間序列資料轉成 AIOps 偵測流程的資料或維運工程師。
- 需要教學版範例資料，而不是只想看 production deployment template 的讀者。

不預設學員有 Kubernetes、雲端平台、Python package 開發或深度學習經驗。

## 學習成果

完成教材後，學員應該能做到：

1. 啟動本機 Prometheus、Grafana 與 exporter，並確認資料真的被抓取。
2. 用 PromQL 查詢 counter、rate、label filtering 與 aggregation。
3. 從 raw network counters 建立可解釋的 time-series features。
4. 比較固定閾值、Z-score、SPC、Isolation Forest 與 forecasting 的適用情境。
5. 把低階 anomaly flags 聚合成較少、較可處理的 alerts。
6. 為 RCA 建立結構化 context，並區分證據、假說與可執行行動。
7. 說明模型輸出如何回到 Prometheus / Grafana / alerting workflow。

## 核心設計問題

這門課不是把幾個 anomaly detection 方法排成清單。主線是：在真實維運環境中，如何把資料、演算法與人類決策組成一個可運作的 AIOps 系統。

每一章都要回到三個問題：

1. **資料問題**：目前的資料是否足以支持這個判斷？缺少拓樸、變更紀錄或業務背景時，演算法應該保守到什麼程度？
2. **演算法問題**：這個方法假設了什麼？固定閾值假設容量邊界已知；Z-score 假設近期 baseline 可信；SPC 假設有穩定製程；Isolation Forest 假設異常在多維空間中比較稀疏；forecasting 假設週期性或趨勢可延續。
3. **架構問題**：這個判斷應該放在哪裡執行？Prometheus rule 適合快速、可解釋、低成本的規則；Python notebook 適合探索與驗證；獨立 scoring service 適合較重的 ML；LLM RCA 應該接在已結構化的 incident context 之後，而不是直接讀 raw time series。

學員每完成一章，都應該能說出一個設計取捨，而不是只得到一張圖。

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

這條路線適合現場課程。它使用 Prometheus 查詢即時本機指標，讓學員先看到自己的機器產生 metrics，再進入特徵工程、異常偵測與 RCA capstone。

建議時間：

| Lab | 主題 | 建議時間 |
| --- | --- | --- |
| `00_observability_stack_and_promql.ipynb` | Prometheus、node_exporter、PromQL | 45-60 分鐘 |
| `01_network_traffic_feature_engineering.ipynb` | EDA、rate、rolling、lag、多解析度 features | 60-75 分鐘 |
| `02_anomaly_detection_and_alerting.ipynb` | 固定閾值、Z-score、deadband、change point | 60-75 分鐘 |
| `08_agentic_ai_rca_capstone.ipynb` | RCA context、agentic loop、human approval gate | 45-60 分鐘 |

### 路線 B：完整自學版

位置：`labs/self-study/`

這條路線適合課後重跑或自學。它主要使用 repository 內建 synthetic data，因此輸出可重建，錯誤也比較容易定位。

建議順序：

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

## 資料流

```text
data/synthetic/synthetic_rrd_metrics.csv
  -> data/processed/features.csv
  -> data/processed/baseline_anomaly_flags.csv
  -> data/processed/spc_results.csv
  -> data/processed/ml_anomaly_scores.csv
  -> data/processed/raw_alerts.csv
  -> data/processed/reduced_alerts.csv
  -> data/processed/forecast_results.csv
```

每個 self-study notebook 會讀取前一步輸出，並把新的中間結果寫回 `data/processed/`。如果中途失敗，先從失敗 notebook 的前一個 lab 重跑，不要直接跳到後面的 lab。

## 演算法與架構設計地圖

| 階段 | 實務問題 | 主要設計決策 | 生產環境位置 |
| --- | --- | --- | --- |
| Lab 00 Observability | 指標是否真的被收集，且可查詢？ | scrape interval、label 設計、資料來源健康檢查 | Prometheus scrape config、Grafana dashboard |
| Lab 01 Feature engineering | raw counters 如何變成可比較的訊號？ | rate、ratio、rolling window、lag、多解析度 | Prometheus recording rules 或 feature service |
| Lab 02 Baseline detection | 哪些偏離值得告警？ | 閾值、baseline 視窗、deadband、誤報預算 | Prometheus alert rules、Grafana annotations |
| Lab 03 SPC | 如何區分隨機波動與製程偏移？ | control limits、EWMA 記憶長度、CUSUM 靈敏度 | rule service 或 batch validation |
| Lab 04 ML anomaly detection | 單一指標看不出來的組合異常如何處理？ | feature set、contamination、解釋方式、重訓頻率 | scoring service，必要時回寫 Prometheus |
| Lab 05 Alert reduction | 如何把大量 flags 變成可處理事件？ | grouping window、problem taxonomy、suppression rule | Alertmanager、event correlation service |
| Lab 06 Forecasting | 能否在 SLA 受影響前提早預警？ | horizon、prediction interval、季節性假設 | forecasting service、capacity planning dashboard |
| Lab 07 RCA | 如何把事件轉成可驗證的根因假說？ | context window、evidence schema、LLM output contract | RCA webhook、ticket enrichment |
| Lab 08 Deployment | 探索邏輯如何進入 24/7 監控？ | 哪些放在 Prometheus，哪些放在 Python service，哪裡保留 human gate | production monitoring pipeline |

這張表是全課的設計骨架。學員在 notebook 中看到的每個參數，都可以回到這張表找它在系統中的位置。

## 教學原則

本教材採用三個原則。

第一，先驗證資料，再談模型。每個 lab 都應該先確認輸入資料、時間範圍、欄位與服務狀態。

第二，偵測方法要和營運決策連在一起。閾值、window、contamination、deadband 與 forecast interval 都不是純技術答案，而是誤報、漏報、反應時間與維運負擔之間的取捨。

第三，AI 只產生假說。RCA 章節中的 LLM 或 agentic AI 不能替代 evidence check。所有建議都要回到 metrics、事件時間與 human approval gate。

## 每章檢核方式

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | conda 環境、notebook JSON、dashboard JSON 是否通過 `validate_setup.py`？ |
| Observability | Prometheus 的 `up` 是否能看到 exporter 與 OS exporter？ |
| Feature engineering | `features.csv` 是否產生？欄位是否能追溯到 raw counters？ |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋？ |
| Alert reduction | raw alerts 是否被合理聚合？是否犧牲了需要立即處理的訊號？ |
| Forecasting | prediction interval 是否太窄或太寬？ |
| RCA | RCA output 是否區分 evidence、hypothesis、recommended action？ |
| Deployment | Grafana dashboard、Prometheus rules 與 notebook 輸出是否對得起來？ |

## 驗證指令

從 repository 根目錄執行：

```bash
conda activate aiops-anomaly-zero-to-hero
python labs/getting-started/scripts/validate_setup.py
```

若只想檢查 clone 下來的教材檔案，不檢查本機服務：

```bash
python labs/getting-started/scripts/validate_setup.py --repo-only
```

Prometheus 設定可用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.yml
promtool check config infra/prometheus/prometheus.windows.yml
```

## 教師使用建議

現場課程不要一開始講完整模型分類。先讓學員在 Lab 00 看到 `up` 與 interface metrics，再逐步說明為什麼 raw counters 不足以直接告警。到 Lab 02 之後，再回頭整理三個層次：資料品質、偵測方法、營運行動。

若時間不足，保留 `workshop/00`、`workshop/01`、`workshop/02`，把 `workshop/08` 作為展示或課後作業。完整自學版則適合要求學員提交 `data/processed/` 產出的 CSV 與一段 RCA 判讀說明。
