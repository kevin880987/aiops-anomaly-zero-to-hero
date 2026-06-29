# Prometheus drop zone

這份文件只說明一件事：notebook 產生 CSV 後，如何用最少步驟讓 Grafana 看到結果。

Cadets 不需要改 Prometheus 設定，不需要寫 exporter，也不需要碰 Grafana JSON。課程已經把這些設定放好。

## 兩個選擇

每個會產生結果的 notebook 都有兩條路。

| 選擇 | 做法 | 適合情境 |
| --- | --- | --- |
| 直接在 notebook 看 | 執行 notebook 內的圖表與表格 | 學演算法、看中間結果、調參數 |
| 放到 Grafana 看 | 把輸出 CSV 複製到 `outputs/prometheus-dropzone/current_results.csv` | 模擬值班 dashboard、看固定 panel、和 Prometheus/Grafana workflow 對齊 |

課堂上可以先看 notebook。需要示範 operational dashboard 時，再走 drop zone。

## 完整資料流

```text
notebook writes a CSV
  -> cadet copies CSV to outputs/prometheus-dropzone/current_results.csv
  -> infra/python_results_exporter.py reads the CSV
  -> exporter exposes http://localhost:8010/metrics
  -> Prometheus scrapes job="python-results-exporter"
  -> Grafana dashboard shows aiops_python_result
```

重點：檔案面向 Prometheus，不是面向 Grafana。Grafana 只查 Prometheus。

## 一次性 setup

先完成：

1. [02-install-prometheus.md](02-install-prometheus.md)
2. [03a-install-grafana-local.md](03a-install-grafana-local.md)

Prometheus 設定檔已經包含：

```text
job_name: python-results-exporter
target: localhost:8010
```

另開一個終端機，從 repository 根目錄啟動 exporter。

macOS / Linux：

```bash
conda activate aiops-anomaly-zero-to-hero
python infra/python_results_exporter.py
```

Windows PowerShell：

```powershell
conda activate aiops-anomaly-zero-to-hero
python infra\python_results_exporter.py
```

如果還沒有 CSV，exporter 會等待。這是正常狀態。

## 每次 notebook 產生結果後

只做一件事：複製 CSV 到 drop zone。

macOS / Linux：

```bash
mkdir -p outputs/prometheus-dropzone
cp <notebook-output.csv> outputs/prometheus-dropzone/current_results.csv
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force outputs\prometheus-dropzone
Copy-Item <notebook-output.csv> outputs\prometheus-dropzone\current_results.csv -Force
```

Exporter 會自動重新讀檔。不用重啟 exporter。

## 常用範例

### ML anomaly score

跑完 Lab 04 後：

```bash
cp outputs/self-study/ml_anomaly_scores.csv outputs/prometheus-dropzone/current_results.csv
```

Grafana / Prometheus query：

```promql
aiops_python_result{column="ml_anomaly_score"}
```

```promql
aiops_python_result{column="ml_is_anomaly"}
```

### Forecast

跑完 Lab 06 後：

```bash
cp outputs/self-study/forecast_results.csv outputs/prometheus-dropzone/current_results.csv
```

Grafana / Prometheus query：

```promql
aiops_python_result{column="y_hat"}
```

```promql
aiops_python_result{column="forecast_30m"}
```

```promql
aiops_python_result{column="early_warning_30m"}
```

### SPC

跑完 Lab 03 後：

```bash
cp outputs/self-study/spc_results.csv outputs/prometheus-dropzone/current_results.csv
```

Grafana / Prometheus query：

```promql
aiops_python_result{column="shewhart_traffic_violation"}
```

```promql
aiops_python_result{column="ewma_discard_violation"}
```

```promql
aiops_python_result{column="cusum_error_violation"}
```

## 檢查是否成功

在 Prometheus 或 Grafana Explore 查：

```promql
up{job="python-results-exporter"}
```

應該是 `1`。

再查：

```promql
aiops_python_result
```

有資料就表示 Grafana 可以顯示。

## 不適合放進 drop zone 的內容

適合：

- anomaly score
- binary flag
- forecast value
- confidence score
- alert count
- severity score

不適合：

- 長文字 RCA explanation
- 大段 JSON report
- stack trace
- debug print

原則：數值結果進 Prometheus，文字脈絡放 notebook、ticket 或 report。
