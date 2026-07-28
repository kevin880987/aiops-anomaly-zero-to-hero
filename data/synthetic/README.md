# Synthetic Data

此資料夾放模擬資料與資料模擬 notebook。

## Files

- `simulator_rrd_metrics.ipynb`：依課程設計產生 30 天、5 分鐘解析度的 synthetic organized network telemetry。
- `synthetic_rrd_metrics.csv`：模擬後的主要時間序列資料。
- `synthetic_event_catalog.csv`：模擬事件 A-J 的事件表。

`labs/workshop/01_network_traffic_feature_engineering.ipynb` 與 `02_anomaly_detection_and_alerting.ipynb` 讀取 `synthetic_rrd_metrics.csv`。
