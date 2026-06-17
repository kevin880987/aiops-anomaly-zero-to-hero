# Labs 路線圖

這個資料夾分成三個區塊。第一次使用先完成 `getting-started/`，再依課程時間選擇 `hands-on/` 或 `full-course/`。

```text
getting-started/  ->  建立 conda 環境，安裝 Prometheus、Grafana、OS exporter
hands-on/         ->  工作坊短版，使用即時 Prometheus 指標
full-course/      ->  完整自學版，使用 repository 內建 synthetic data
```

## 先做環境設定

請從 [`getting-started/README.md`](getting-started/README.md) 開始。它會帶你完成：

1. 建立 `aiops-anomaly-zero-to-hero` conda 環境。
2. 啟動 `exporter.py`，讓 Prometheus 可抓取課程 synthetic metrics。
3. 安裝並啟動 Prometheus。
4. 視課程路徑安裝 node_exporter 或 windows_exporter。
5. 安裝 Grafana，連接 Prometheus，匯入 dashboard。

## 路徑 A：工作坊短版

適合現場教學。它用 Prometheus 查詢本機 OS metrics，再把觀念帶到異常偵測與 RCA。

建議順序：

1. `hands-on/00_observability_stack_and_promql.ipynb`
2. `hands-on/01_network_traffic_feature_engineering.ipynb`
3. `hands-on/02_anomaly_detection_and_alerting.ipynb`
4. `hands-on/08_agentic_ai_rca_capstone.ipynb`

這條路徑需要 Prometheus 正在執行。Lab 00 也需要 macOS / Linux 的 node_exporter，或 Windows 的 windows_exporter。

## 路徑 B：完整自學版

適合課後完整重跑。它主要使用 repository 內建的 synthetic CSV，因此每一步都能從固定資料重建輸出。

建議順序：

1. `../data/synthetic/simulator_rrd_metrics.ipynb`
2. `full-course/00_observability_stack.ipynb`
3. `full-course/01_time_series_features.ipynb`
4. `full-course/02_baseline_anomaly_detection.ipynb`
5. `full-course/03_spc_anomaly_detection.ipynb`
6. `full-course/04_ml_anomaly_detection.ipynb`
7. `full-course/05_alert_reduction.ipynb`
8. `full-course/06_forecasting.ipynb`
9. `full-course/07_root_cause_analysis.ipynb`
10. `full-course/08_deploy_to_production.ipynb`

`data/processed/` 會保存中間輸出。若你想重新產生結果，依上列順序重跑 notebooks 即可。

## 選哪一條？

如果你正在上工作坊，選 `hands-on/`。如果你要確認整套 pipeline 的資料流，或想在沒有現場時間限制下完整練習，選 `full-course/`。
