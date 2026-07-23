# 工作坊下午場：從 telemetry 到 alert

上午的理論說，anomaly 是在脈絡下相對於一條明確 baseline 的偏離。下午把這句話變成可以執行的東西：你會親手選 baseline、算 score、把 score 收成 label、讓 label 通過 policy 變成 alert，最後用 event-level recall 與 alerts per day 去評這套設定值不值得帶進值班室。整個下午只有一條資料路徑，notebook 算完結果寫進 drop zone，exporter 曝露成 metric，Prometheus 抓，Grafana 查。

這是 GUI-first 的課。Notebook 負責計算與發佈，時間序列圖在 Grafana 上，notebook 不畫圖。

## 從 Lab 00 開始

Lab 00 要先跑完，它唯一要證明的事是 Python 算出來的數字能到 Grafana 螢幕上；這條路不通，Lab 01 與 Lab 02 只會得到空的 dashboard。

Grafana 這一端由一行指令裝好，它建立 Prometheus datasource、`AIOps Workshop` folder、三個 dashboard、三條 alert rule，以及 mute timing `aiops-maintenance-window`：

```bash
python infra/setup_grafana.py
```

四個服務怎麼起、replay clock 的倍速代表什麼、以及所有的 troubleshooting，都寫在 `00_observability_stack_and_promql.ipynb` 裡。卡住的時候回那份 notebook，不要回這一頁。

## 下午三節

| Lab | 主題 | Notebook | Dashboard 標題與 uid |
| --- | --- | --- | --- |
| 00 | 觀測堆疊與 PromQL。把一個數字送上 Grafana，故意弄壞它，再從 dashboard 上讀出斷在哪一跳 | `00_observability_stack_and_promql.ipynb` | `Lab 00 - Pipeline check`，uid `aiops-lab00` |
| 01 | 網路流量 feature engineering。同一段流量對四種 baseline 比較：rolling mean、median 與 MAD、same seasonal position、peer group | `01_network_traffic_feature_engineering.ipynb` | `Lab 01 - Features and baselines`，uid `aiops-lab01` |
| 02 | 偵測與告警。偏離量收斂成 score，設門檻得到 label，加上 duration、minimum volume 與 maintenance exclusion 才成為 alert，最後用 scorecard 檢查代價 | `02_anomaly_detection_and_alerting.ipynb` | `Lab 02 - Detection, scores and alerts`，uid `aiops-lab02` |

Dashboard 網址是 <http://localhost:3000/d/aiops-lab00> 這種形式，把 uid 換掉即可。Lab 01 與 Lab 02 的 dashboard 上方有一個 `Port` 下拉選單，可以在五個 port 之間切換；Lab 00 沒有，它只發佈一條 toy signal。

順序不能跳。Lab 02 的 evidence panel 畫的是 Lab 01 算出來的 baseline，沒有 Lab 01 的欄位，Lab 02 的 dashboard 只有一半。

## 這個目錄裡的第四份 notebook

`08_agentic_ai_rca_capstone.ipynb` 不屬於下午這三節，時間也排不進去。它接在 Lab 02 的
alert 之後，處理的是「告警發出來以後怎麼查」：把偵測結果整理成 incident context，交給一個
在課堂版裡以 deterministic mock 執行的 agent 做 root cause analysis，不需要任何 API token。
它跟前三節共用同一份 telemetry、同一個 `aiopskit`，也共用 drop zone，所以跑完它會蓋掉
Grafana 上 Lab 02 的欄位。想留著 Lab 02 的畫面就先看完，或事後重跑 Lab 02 最後一格。
