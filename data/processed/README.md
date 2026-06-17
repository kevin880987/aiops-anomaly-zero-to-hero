# Processed Data

此資料夾放 Notebook pipeline 的輸出結果。

## Files

- `features.csv`：`labs/full-course/01_time_series_features.ipynb` 產生的 rolling statistics、lag、rate 與 ratio features。
- `baseline_anomaly_flags.csv`：`labs/full-course/02_baseline_anomaly_detection.ipynb` 產生的 baseline anomaly flags。
- `spc_results.csv`：`labs/full-course/03_spc_anomaly_detection.ipynb` 產生的 SPC control chart results。
- `ml_anomaly_scores.csv`：`labs/full-course/04_ml_anomaly_detection.ipynb` 產生的 unsupervised ML anomaly scores。
- `raw_alerts.csv`：`labs/full-course/05_alert_reduction.ipynb` 產生的低階 raw alerts。
- `reduced_alerts.csv`：`labs/full-course/05_alert_reduction.ipynb` 聚合後的 reduced alerts。
- `forecast_results.csv`：`labs/full-course/06_forecasting.ipynb` 產生的 forecast 與 early warning results。
部分 RCA 表格會在 notebook 執行過程中即時計算與展示；若本資料夾沒有 RCA 事件檔，請重新執行 `labs/full-course/07_root_cause_analysis.ipynb` 查看當次結果。
