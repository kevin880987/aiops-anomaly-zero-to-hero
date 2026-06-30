# Data Directory

此資料夾依來源與生命週期分開保存課程資料。

## Structure

- `synthetic/`：主教材使用的 organized network telemetry CSV 與資料模擬 notebook。Labs 從這裡讀取原始資料。
- `sample/`：選讀資料。三竹提供的 LibreNMS / RRDTool sample `.rrd` 檔，用來理解真實原始格式。初學者可略過。

若要重建 synthetic data，執行：

```bash
jupyter lab data/synthetic/simulator_rrd_metrics.ipynb
```

依序執行所有 cells，會更新 `data/synthetic/synthetic_rrd_metrics.csv` 與 `data/synthetic/synthetic_event_catalog.csv`。
