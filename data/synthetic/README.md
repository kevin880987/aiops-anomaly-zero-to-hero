# Synthetic Data

此資料夾放模擬資料與資料模擬 notebook。

## Files

- `simulator_rrd_metrics.ipynb`：依課程設計產生 30 天、5 分鐘解析度的 synthetic organized network telemetry。
- `synthetic_rrd_metrics.csv`：模擬後的主要時間序列資料。
- `synthetic_event_catalog.csv`：模擬事件 A-J 的事件表。

後續 `labs/self-study/01_time_series_features.ipynb` 會讀取 `synthetic_rrd_metrics.csv`，並將特徵與分析結果輸出到 `outputs/self-study/`。
