# Prometheus drop zone（自學版路線）

這份文件說明自學版 notebook 產生結果 CSV 之後，如何讓 Grafana 看到結果。

> **工作坊短版不走這條路。** `labs/workshop/` 的 notebook 直接把 CSV 與 PNG 寫進
> `outputs/workshop/`，用 `python -m http.server 8080 --directory outputs/workshop` 開出來，
> Grafana 端用 Infinity datasource 讀檔案。那條路徑沒有 exporter，也沒有 drop zone，
> 說明在 [`labs/workshop/README.md`](../workshop/README.md)。

自學版走 drop zone 是有理由的：它示範的正是 pull 模型的完整形狀，
從 exporter 曝露 `/metrics`，到 Prometheus scrape，到 Grafana 查詢。
Cadets 不需要改 Prometheus 設定，也不需要碰 Grafana JSON，課程已經把這些設定放好。

## 兩個選擇

每個會產生結果的 notebook 都有兩條路。

| 選擇 | 做法 | 適合情境 |
| --- | --- | --- |
| 直接在 notebook 看 | Python 讀取整理好的 telemetry CSV，執行 notebook 內的圖表與表格 | 學演算法、看中間結果、調參數 |
| 放到 Grafana 看 | 手動複製 CSV 到 `outputs/prometheus-dropzone/current_results.csv` | 模擬值班 dashboard、看固定 panel、和 Prometheus/Grafana workflow 對齊 |

課堂上可以先看 notebook。需要示範 operational dashboard 時，再走 drop zone。

## 完整資料流

```text
Python notebook reads organized telemetry CSV
  -> notebook writes a result CSV
  -> the cadet copies the CSV to outputs/prometheus-dropzone/current_results.csv
  -> infra/python_results_exporter.py reads it
  -> exporter exposes http://localhost:8010/metrics
  -> Prometheus scrapes job="python-results-exporter"
  -> Grafana dashboard shows aiops_python_result
```

重點：drop zone 檔案面向 Prometheus，不是面向 Grafana。Grafana 只查 Prometheus。Python 的 beginner path 主要讀 CSV；PromQL 是營運查詢語言，不是本課程演算法開發的主要輸入。

## 一次性 setup

先完成：

1. [02-install-prometheus.md](02-install-prometheus.md)
2. [03a-install-grafana-local.md](03a-install-grafana-local.md)

設定檔裡這個 job 預設是註解掉的，因為工作坊路線不需要它。先在自己作業系統對應的 `infra/prometheus/prometheus.*.yml` 裡把它打開：

```yaml
  - job_name: "python-results-exporter"
    static_configs:
      - targets: ["localhost:8010"]
```

改完重啟 Prometheus，或在有 `--web.enable-lifecycle` 的情況下 `curl -X POST http://localhost:9090/-/reload`。用 `brew services` 啟動的話，記得設定檔改的是 `/opt/homebrew/etc/prometheus.yml` 那一份，或重新複製一次。

接著另開一個終端機，從 repository 根目錄啟動 exporter。

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
