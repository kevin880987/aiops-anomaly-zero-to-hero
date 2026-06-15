# Data Directory

此資料夾依來源與生命週期分開保存課程資料。

## Structure

- `synthetic/`：模擬產生的 RRD-like network metrics，以及資料模擬 notebook。
- `sample/`：外部提供的 LibreNMS / RRDTool sample data。
- `processed/`：Notebook1-7 產生的 features、anomaly flags、SPC、ML scores、alerts、forecast 與 RCA outputs。

`processed/` 內容可由 notebooks 重建。`synthetic/` 也可執行下列指令重建：

```bash
aiops-simulate --days 30 --seed 42 --out-dir data/synthetic
```
