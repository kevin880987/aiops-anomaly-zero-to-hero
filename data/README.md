# Data Directory

此資料夾依來源與生命週期分開保存課程資料。

## Structure

- `synthetic/`：模擬產生的 RRD-like network metrics，以及資料模擬 notebook。
- `sample/`：外部提供的 LibreNMS / RRDTool sample data。
- `processed/`：`labs/full-course/01` 到 `07` 產生的 features、anomaly flags、SPC、ML scores、alerts、forecast 與 RCA outputs。

`processed/` 內容可由 notebooks 重建。若要重建 synthetic data，請執行：

```bash
jupyter lab data/synthetic/simulator_rrd_metrics.ipynb
```

打開 notebook 後依序執行所有 cells，會更新 `data/synthetic/synthetic_rrd_metrics.csv` 與 `data/synthetic/synthetic_event_catalog.csv`。
