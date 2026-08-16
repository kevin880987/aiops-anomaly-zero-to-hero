# 工作坊下午場：從 telemetry 到 alert

上午把 anomaly 定義成在脈絡下相對於一條明確 baseline 的偏離。下午把這個定義變成可以執行的
步驟：親手選 baseline、算 score、把 score 收成 label、讓 label 經過 policy 篩選才成為 alert，最後用
event recall 與 alerts per day 去評這套設定值不值得帶進值班室。

## pipeline 的五個環節

Lab 00 把這條 pipeline 接起來，之後不再動它。

![Lab 00 的資料流](../../diagrams/lab00_pipeline.svg)

`node_exporter` 曝露這台機器的網路 counter，Prometheus 每 5 秒抓一次。
[`detector.py`](detector.py) 反過來向 Prometheus 查詢這段流量，算出偏離分數，再把分數曝露成
`/metrics`，於是 Prometheus 把它當成一般指標抓回去。Grafana 用 PromQL 查詢分數，
`infra/prometheus/alerts.yml` 的規則也直接打在分數上。

除了 `detector.py`，pipeline 上每一個元件都是官方軟體。分數送回 Prometheus 之後，下游沒有任何
一格知道它是 Python 算的，這一點是刻意設計的，因為上線要換的只有演算法，pipeline 可以原封不動。

所以 Lab 01 與 Lab 02 都只做一件事，把 `detector.py` 裡 `rolling_zscore()` 那個函式換成撐得住
真實流量的版本。Lab 01 決定基線該怎麼算，Lab 02 決定分數之外還要包什麼政策才配送出去。

## Lab 01 與 Lab 02 的資料來源

Lab 01 與 Lab 02 讀的是 `data/synthetic/synthetic_rrd_metrics.csv`，五個 port、一整個月、
十八個標好的事件。用歷史資料是因為演算法要拿有真值的資料去量，而 Lab 00 的 pipeline 上跑的是這台
機器此刻的流量，沒有真值可比。

這兩份 notebook 全程用 matplotlib 畫圖，產出留在 notebook 裡。定住的圖適合逐條比較，Grafana
上那三張 panel 畫的是即時的線，適合換條件驗證。

三種偵測方法的取捨見 [`../../diagrams/lab02_detection_methods.svg`](../../diagrams/lab02_detection_methods.svg)。

## 開課前要維持執行的四個服務

前三個安裝完成後就常駐執行，第四個在 Lab 00 第 4 節啟動，啟動之後整個下午都留著。

```bash
brew services start prometheus     # http://localhost:9090
brew services start grafana        # http://localhost:3000
brew services start node_exporter  # http://localhost:9100/metrics

# 在 repo 根目錄，這個視窗留著
python labs/workshop/detector.py   # http://localhost:9200/metrics
```

Prometheus 要讀這個 repo 的設定，才會有 `aiops-detector` 這個 job 與告警規則：

```bash
cp infra/prometheus/prometheus.macos.yml /opt/homebrew/etc/prometheus.yml
cp infra/prometheus/alerts.yml           /opt/homebrew/etc/alerts.yml
curl -X POST http://localhost:9090/-/reload
```

Linux 與 Windows 的對應做法見 [`labs/getting-started/02-install-prometheus.md`](../getting-started/02-install-prometheus.md)。
Windows 的 exporter 是 `windows_exporter`，聽在 9182，設定檔用 `prometheus.windows.yml`。

## Grafana 這一端

只有 Prometheus 一個 datasource，在 setup 那一步就設定完成。原始速率存在裡面，偏離分數與
告警狀態也一樣，所以 Grafana 這一端一律用 PromQL 查詢。

三張 panel 在 Lab 00 逐格建立，做法寫在 [`dashboard.md`](dashboard.md)。
`infra/grafana/dashboards/aiops-workshop.json` 是建完之後核對用的答案卷。

## 下午三節，加上第六週的兩節

| Lab | 主題 | Notebook |
| --- | --- | --- |
| 00 | 把線接起來。counter 與 rate、`up`、Python 服務怎麼進到 Prometheus、`for:` 怎麼擋掉雜訊，故意弄壞四次再讀出斷在哪 | `00_end_to_end_pipeline.ipynb` |
| 01 | 網路流量 feature engineering。同一段流量對四種 baseline 比較：rolling mean、median 與 MAD、same seasonal position、peer group | `01_network_traffic_feature_engineering.ipynb` |
| 02 | 偵測與告警。偏離量收斂成 score，設門檻得到 label，加上 duration、minimum volume 與 maintenance exclusion 才成為 alert，最後用 scorecard 檢查代價 | `02_anomaly_detection_and_alerting.ipynb` |
| 06 | 預測與預警。主模型 Prophet 學「這個時刻的正常是多少」,殘差模型 XGBoost 學「不正常正在往哪裡走」,兩個相加碰到容量門檻就發預警; 含階數的交叉驗證、horizon 的挑法、分位數區間與四級警戒，最後用沒調過參數的事件驗一次 | `06_forecasting.ipynb` |
| 07 | Hybrid 根因分析。幅度、位置、關聯、時序、可預測性五種證據，四項等權合成排名，交給 LLM 做證據整合 (沒有 API 金鑰時重播錄好的回應),再用可抽換的 domain 知識包 (RAG) 接上領域知識並換一個產業，最後用 hit@k、MRR 與名次差距分組評估。兩章的結果都在這一章接上 Grafana | `07_root_cause_analysis.ipynb` |

順序不能跳。Lab 02 的分數建立在 Lab 01 算出來的 baseline 欄位上，Lab 06 的殘差建立在同一組特徵上，Lab 07 讀 Lab 06 的輸出。

## notebook 裡的 toolkit

每一份 notebook 開頭有 toolkit cell，載入、baseline、偵測器、alert policy、事件評估的函式都寫在
那裡，可以直接閱讀與修改。這門課不把它們收進要另外理解的函式庫，資料科學的邏輯留在 notebook
裡，不藏在 `import` 後面。

五份 notebook 各自帶自己需要的函式，所以有些函式會重複出現。重複是為了讓每一份 notebook 都能
單獨開啟、單獨讀完。唯一的例外是 Lab 00，它直接 `import` `detector.py` 裡的函式，因為那一節要
說明的正是「notebook 裡試的那一段，跟服務跑的是同一段」。
