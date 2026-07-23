# Prometheus drop zone

這份文件只說明一件事：Python notebook 產生結果 CSV 後，如何用最少步驟讓 Grafana 看到結果。

Cadets 不需要改 Prometheus 設定，不需要寫 exporter，也不需要碰 Grafana JSON。課程已經把這些設定放好。

## 兩個選擇

每個會產生結果的 notebook 都有兩條路。

| 選擇 | 做法 | 適合情境 |
| --- | --- | --- |
| 直接在 notebook 看 | Python 讀取整理好的 telemetry CSV，執行 notebook 內的圖表與表格 | 學演算法、看中間結果、調參數 |
| 放到 Grafana 看 | 由 `wk.publish()` 寫入，或手動複製 CSV 到 `outputs/prometheus-dropzone/current_results.csv` | 模擬值班 dashboard、看固定 panel、和 Prometheus/Grafana workflow 對齊 |

課堂上可以先看 notebook。需要示範 operational dashboard 時，再走 drop zone。

## 完整資料流

```text
Python notebook reads organized telemetry CSV
  -> notebook writes a result CSV
  -> the CSV lands at outputs/prometheus-dropzone/current_results.csv
       workshop labs: wk.publish() writes it, plus current_results.manifest.json
       self-study:    cadet copies it in by hand, no manifest
  -> infra/python_results_exporter.py reads the CSV, and the manifest if there is one
  -> exporter exposes http://localhost:8010/metrics
  -> Prometheus scrapes job="python-results-exporter"
  -> Grafana dashboard shows aiops_python_result
```

重點：drop zone 檔案面向 Prometheus，不是面向 Grafana。Grafana 只查 Prometheus。Python 的 beginner path 主要讀 CSV；PromQL 是營運查詢語言，不是本課程演算法開發的主要輸入。

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

工作坊短版請改用 `REPLAY_SPEED_X=720 python infra/python_results_exporter.py`。這個環境變數決定三十天資料重演成幾分鐘，說明見 [`labs/workshop/README.md`](../workshop/README.md)。

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

## Workshop 路線：wk.publish() 與 manifest

工作坊短版的 notebook 不用手動 `cp`。它呼叫 `aiopskit` 的 publish：

```python
wk.publish(frame, columns=["score_robust", "label", "alert"], name="lab02_detection")
```

這一行寫出三個檔案。`outputs/workshop/lab02_detection.csv` 是存檔，跑完之後還在，可以回頭比對。`outputs/prometheus-dropzone/current_results.csv` 是 exporter 監看的那一份。第三個是 `outputs/prometheus-dropzone/current_results.manifest.json`，內容長這樣：

```json
{
  "source": "lab02_detection",
  "value_columns": ["score_robust", "label", "alert"],
  "label_columns": ["device_id", "port_id", "port_role", "event_label"],
  "rows": 43200,
  "sim_start": "2026-02-01 00:00:00",
  "sim_end": "2026-03-02 23:55:00",
  "generated_at": "2026-07-23T04:38:14+00:00"
}
```

Manifest 存在的理由是 exporter 沒有它就得用猜的。沒有 manifest 時，exporter 先比對一份內建的常用欄位清單，都對不上就退回「取前八個數值欄位」。這個行為在只發佈三、四個欄位時沒問題，一旦一個 lab 發佈三十幾個欄位而你要看的那個排在第十二位，它就會安靜地消失。有 manifest，exporter 就照 `value_columns` 逐欄發佈，不多也不少。`label_columns` 同理，決定哪些欄位變成 Prometheus label，其餘固定送空字串，因為 gauge 的 label 集合在建立時就固定了。

`publish()` 還處理兩件雜事。布林欄位會轉成 1 和 0，這樣 Grafana 的 state panel 才畫得出來。傳給 `scalars=` 的單一數值（例如 event recall、alerts per day）會被廣播到每一列，讓 stat panel 可以像查一般 series 一樣查到它。

一次只有一個 lab 是活的。`current_results.csv` 只有一份，任何一次 `publish()` 都會覆蓋上一次的內容，前一個 lab 的 dashboard 就會空掉。工作坊的處理方式是後面的 lab 一併發佈前面 lab 需要的欄位，細節見 [`labs/workshop/README.md`](../workshop/README.md)。

手動 `cp` 進去的 CSV 沒有 manifest，走的是猜欄位那條路。想明確指定欄位又不想改 notebook，可以在啟動 exporter 時用環境變數覆蓋，它的優先權高於 manifest：

```bash
RESULT_COLUMNS=y_hat,y_hat_lower,y_hat_upper python infra/python_results_exporter.py
```

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
