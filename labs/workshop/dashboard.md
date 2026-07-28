# 建這門課的 dashboard

這門課的 dashboard 一格一格自己建。理由是三個 lab 讀的檔案不是同時存在：
Lab 01 與 Lab 02 的 CSV 要執行過那份 notebook 才會出現，匯入整份只會看到一堆空 panel。
`infra/grafana/dashboards/aiops-workshop.json` 留著，是建完之後核對用的答案卷，卡在某張 panel
的設定上可以打開來看對應 id，不要在任何一個 lab 裡把它整份匯入。

**前提：** Datasource 與 Infinity 外掛在 setup 就安裝完成了，做法見
[`labs/getting-started/03-install-grafana-local.md`](../getting-started/03-install-grafana-local.md)。
`Connections > Data sources` 應該列得出 `Prometheus` 與 `Lab outputs` 兩筆，缺哪一筆就回那份文件補。

## Lab 00：建 dashboard 與第一列（Prometheus）

**建立 dashboard 與第一個變數。** Dashboards > New > New dashboard > Add visualization，datasource 選
Prometheus。存檔（Ctrl/Cmd+S）取個名字，例如 `AIOps workshop`。再開 dashboard 右上角的齒輪
Settings > Variables > New variable：Name 填 `iface`，Type 選 `Query`，datasource 選 Prometheus，
Query 填 `label_values(node_network_receive_bytes_total, device)`，存檔。左上角現在會多一個
**iface** 下拉，選 notebook 第 4 節找出來的那張介面。

**第一張 panel：Throughput, receive and transmit。** 回到 dashboard，Edit panel，Query 貼：

```promql
rate(node_network_receive_bytes_total{device="$iface"}[1m])
rate(node_network_transmit_bytes_total{device="$iface"}[1m])
```

兩條 query 的 Legend 分別填 `receive`、`transmit`。Panel options 的 Title 填同樣的名字，
Standard options 的 Unit 選 `Bytes/sec (Bps)`。

**第二張 panel：Mean packet size。** Add > Visualization，同一個 datasource，Query 貼：

```promql
(rate(node_network_receive_bytes_total{device="$iface"}[1m]) + rate(node_network_transmit_bytes_total{device="$iface"}[1m]))
  / clamp_min(rate(node_network_receive_packets_total{device="$iface"}[1m]) + rate(node_network_transmit_packets_total{device="$iface"}[1m]), 1)
```

Legend 填 `mean packet size`，Unit 選 `bytes (SI)`。這條把兩個方向的 bytes 加總除以兩個方向的封包數，
分母加 `clamp_min(..., 1)` 是防止沒有封包時除以零。

兩張 panel 現在應該立刻有線；沒有線就回 Explore 查詢 `up` 是不是 1。這兩張是第一列的全部，讀的是
Prometheus。第二列與第三列讀 `outputs/workshop/` 裡的檔案，Lab 01 開始建，因為那些檔案下一個 lab
才寫出來。那兩列的欄位名是 `aiops_traffic_bps` 這種 metric 名，port 用一個叫 `Port` 的變數篩選，
寫成 `port_id == "$port"`，對應的就是 PromQL 的 `{port_id="..."}`。Grafana 這一側刻意與 Prometheus
維持相同形態，將來把 datasource 換過去，panel 不用重做。

**第三張 panel（第二列第一張）：Lab 00 toy signal against its baseline。** 先在瀏覽器打開
<http://localhost:8080/lab00_toy_signal.csv>，顯示得出內容 Grafana 才讀取得到；顯示不出來就是
檔案伺服器沒有啟動，或啟動在別的資料夾。確認之後 Add > Visualization，datasource 選
`Lab outputs`，Type 選 `CSV`，Source 選 `URL`，URL 填 `http://localhost:8080/lab00_toy_signal.csv`，
Parser 選 Backend，欄位設 `timestamp` 為 Timestamp、`toy_value` 與 `toy_baseline` 為 Number。
Title 填 `Lab 00  toy signal against its baseline`，存檔。時間範圍選 Last 7 days，
`synthetic_wave()` 產生的時間戳是從現在往回算 5 天，預設的 Last 30 minutes 顯示不出資料。
第二列其餘的 panel 從 Lab 01 開始建。

## Lab 01：第二列的主要 panel

**先加一個變數。** `lab01_baselines.csv` 把 5 個 port 疊在同一個檔案裡，所以 panel 一定要篩。
Dashboard settings > Variables > New variable，Name 填 `port`，Type 選 `Custom`，Values 填
`port-id7427,port-id7428,port-id7429,port-id7430,port-id7431`，存檔。左上角現在多一個
**port** 下拉。

**第四張 panel：Lab 01  traffic against four baselines。** Add > Visualization，datasource 選
`Lab outputs`，Type 選 `CSV`，Source 選 `URL`，URL 填
`http://localhost:8080/lab01_baselines.csv`，Parser 選 Backend。Columns 依序加：

| CSV 欄位 | 顯示名稱 | 型別 |
| --- | --- | --- |
| `timestamp` | `time` | Timestamp |
| `traffic_bps` | `aiops_traffic_bps` | Number |
| `roll_center` | `aiops_baseline_rolling_bps` | Number |
| `robust_center` | `aiops_baseline_robust_bps` | Number |
| `seasonal_center` | `aiops_baseline_seasonal_bps` | Number |
| `peer_center` | `aiops_baseline_peer_bps` | Number |

Query 下方展開 Filter，`filterExpression` 填 `port_id == "$port"`。**不要用 query 編輯器的
Filter 欄位**，backend parser 不會套用，畫面上看起來像設定好了，回來的仍是 5 個 port 疊在一起的
43200 列，只有 `filterExpression` 這個欄位真的會篩。Title 填同樣的名字，存檔。

**第五張 panel：Lab 01  the robust band, and what it swallows。** 同樣的 URL 與 Parser，
Columns 換成 `timestamp`→`time`、`traffic_bps`→`aiops_traffic_bps`、`robust_lo`→
`aiops_baseline_robust_lo_bps`、`robust_hi`→`aiops_baseline_robust_hi_bps`，`filterExpression`
一樣填 `port_id == "$port"`。

`filterExpression` 這個式子對應的就是 PromQL 的 `{port_id="..."}`。上線之後 datasource 換成
Prometheus，篩選的寫法會變，選中的資料列不變。

**第六張 panel：Quality features: error and discard rate。** 同樣 datasource `Lab outputs`，
URL 一樣是 `http://localhost:8080/lab01_baselines.csv`，Columns 加 `timestamp`→`time`、
`error_rate`→`aiops_error_rate`、`discard_rate`→`aiops_discard_rate`，`filterExpression`
填 `port_id == "$port"`。

**選用的診斷 panel：peer baseline 的盲點。** 驗證 peer baseline 對哪種形狀視而不見時用，不是
主要的六張之一。同樣 datasource 與 URL，欄位選 `timestamp`、`broadcast_ratio`、`port_id`，
`filterExpression` 填 `port_id == "port-id7427" || port_id == "port-id7429"`，時間範圍對到
2026-02-19 11:00 到 13:00。

## Lab 02：第二列剩下的 panel 與四張 stat panel

**第七張 panel：Lab 02  score layers。** Add > Visualization，datasource 選 `Lab outputs`，
Type 選 `CSV`，Source 選 `URL`，URL 填 `http://localhost:8080/lab02_detection.csv`，Parser 選
Backend。Columns：

| CSV 欄位 | 顯示名稱 | 型別 |
| --- | --- | --- |
| `timestamp` | `time` | Timestamp |
| `score_rolling` | `aiops_score_rolling` | Number |
| `score_robust` | `aiops_score_robust` | Number |
| `score_seasonal` | `aiops_score_seasonal` | Number |
| `score_peer` | `aiops_score_peer` | Number |
| `score_max` | `aiops_score_max` | Number |

`filterExpression` 填 `port_id == "$port"`，跟 Lab 01 用的是同一個變數。Title 填同樣的名字，存檔。

**第八張 panel：Lab 02  breach, label, alert。** 同樣的 URL 改成 `lab02_detection.csv`，Columns
換成 `timestamp`→`time`、`breach`→`aiops_breach`、`label`→`aiops_label`、`alert`→`aiops_alert`、
`is_incident`→`aiops_incident`，`filterExpression` 一樣填 `port_id == "$port"`。

**四張 stat panel。** 都讀 `http://localhost:8080/lab02_scorecard.csv`，這個檔案沒有 `port_id`
欄位，不用填 `filterExpression`。Type 選 `Stat`，四張各自只有一欄：

| Panel 標題 | CSV 欄位 | 顯示名稱 |
| --- | --- | --- |
| Event recall | `event_recall` | `aiops_event_recall` |
| Alerts per day | `alerts_per_day` | `aiops_alerts_per_day` |
| Detection delay | `mttd_min` | `aiops_detection_delay_minutes` |
| Unexplained alerts | `false_unexplained` | `aiops_unexplained_alerts` |

卡在某張 panel 的設定上，`infra/grafana/dashboards/aiops-workshop.json` 裡有對應 id 的完整設定
可以核對。

## 排查

| 症狀 | 先查詢 |
| --- | --- |
| 第一列 panel 全空 | Explore 裡查詢 `up`。是 0 就是 exporter 沒起或 Prometheus 沒抓到 |
| 第一列有線但形狀是斜坡 | 查詢忘了包 `rate()` |
| 第二列 panel 報 connection refused | 檔案伺服器沒開，回 Lab 00 那份 notebook 第 1 節的指令 |
| 第二列 panel 報 404 | 檔名或路徑錯了，直接在瀏覽器開 <http://localhost:8080> 對一次 |
| 第二列 panel 沒錯誤但空白 | 時間範圍。Lab 00 的假訊號是最近 5 天，Lab 01 與 Lab 02 是 2026 年 2 月 |
| Infinity 這個 datasource 不存在 | 外掛沒有安裝成功，或安裝完沒重啟 Grafana，回 setup 那份文件 |
| 重新整理後剛才建的 panel 不見了 | 沒有存 dashboard，Ctrl/Cmd+S 存一次 |
