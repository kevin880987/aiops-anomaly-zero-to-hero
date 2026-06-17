# Labs 路線圖

這個資料夾分成三個區塊。第一次使用先完成 `getting-started/`，再依課程時間選擇 `self-study/` 或 `workshop/`。

```text
getting-started/  ->  建立 conda 環境，安裝 Prometheus、Grafana、OS exporter
workshop/         ->  工作坊短版，使用即時 Prometheus 指標
self-study/       ->  完整自學版，使用 repository 內建 synthetic data
```

Shared pipeline diagrams live in `labs/self-study/diagrams/`。`labs/workshop/diagrams/` 只保留工作坊專用圖，避免同一張圖在兩個地方維護。

## 先做環境設定

請從 [`getting-started/README.md`](getting-started/README.md) 開始。它會帶你完成：

1. 建立 `aiops-anomaly-zero-to-hero` conda 環境。
2. 啟動 `infra/exporter.py`，讓 Prometheus 可抓取課程 synthetic metrics。
3. 安裝並啟動 Prometheus。
4. 視課程路徑安裝 node_exporter 或 windows_exporter。
5. 安裝 Grafana，連接 Prometheus，匯入 dashboard。

## 路徑 A：工作坊短版

適合現場教學。它用 Prometheus 查詢本機 OS metrics，再把觀念帶到異常偵測與 RCA。

建議順序：

1. `workshop/00_observability_stack_and_promql.ipynb`
2. `workshop/01_network_traffic_feature_engineering.ipynb`
3. `workshop/02_anomaly_detection_and_alerting.ipynb`
4. `workshop/08_agentic_ai_rca_capstone.ipynb`

這條路徑需要 Prometheus 正在執行。Lab 00 也需要 macOS / Linux 的 node_exporter，或 Windows 的 windows_exporter。

## 路徑 B：完整自學版

適合課後完整重跑。它主要使用 repository 內建的 synthetic CSV，因此每一步都能從固定資料重建輸出。

建議順序：

1. `../data/synthetic/simulator_rrd_metrics.ipynb`
2. `self-study/00_observability_stack.ipynb`
3. `self-study/01_time_series_features.ipynb`
4. `self-study/02_baseline_anomaly_detection.ipynb`
5. `self-study/03_spc_anomaly_detection.ipynb`
6. `self-study/04_ml_anomaly_detection.ipynb`
7. `self-study/05_alert_reduction.ipynb`
8. `self-study/06_forecasting.ipynb`
9. `self-study/07_root_cause_analysis.ipynb`
10. `self-study/08_deploy_to_production.ipynb`

`data/processed/` 會保存中間輸出。若你想重新產生結果，依上列順序重跑 notebooks 即可。

## 選哪一條？

如果你正在上工作坊，選 `workshop/`。如果你要確認整套 pipeline 的資料流，或想在沒有現場時間限制下完整練習，選 `self-study/`。

## 每個 lab 的思考方式

不要只把 notebook 跑完。每一章都要回答一個設計問題：

| Lab | 要回答的設計問題 |
| --- | --- |
| 00 | 這些指標是否真的代表我要監控的系統？scrape interval 與 label 設計是否支援後續分析？ |
| 01 | 哪些 raw counters 應該轉成 rate、ratio、rolling baseline 或 lag feature？ |
| 02 | 告警閾值如何對應到誤報、漏報與 on-call 負擔？ |
| 03 | SPC 規則是否能抓到慢性偏移，而不是只抓單點尖峰？ |
| 04 | ML 模型是否真的增加偵測能力，還是只讓系統更難解釋？ |
| 05 | 降噪規則是否把同一事件合併起來，同時沒有遮蔽需要立刻處理的訊號？ |
| 06 | 預測 horizon 與 prediction interval 是否符合實際反應時間？ |
| 07 / 08 | RCA 或 agentic AI 是否使用結構化證據，且在執行行動前保留 human approval gate？ |

如果學員無法回答這些問題，代表還沒有真正完成該 lab。
