# 工作坊下午場：從 telemetry 到 alert

上午的理論說，anomaly 是在脈絡下相對於一條明確 baseline 的偏離。下午把這句話變成可以執行的東西：你會親手選 baseline、算 score、把 score 收成 label、讓 label 通過 policy 變成 alert，最後用 event-level recall 與 alerts per day 去評這套設定值不值得帶進值班室。

## 兩條資料路徑

下午的每一個數字都會出現在 Grafana 上，走的是兩條不同的路。分開的理由是儲存模型，不是偏好。

**即時路徑。** `node_exporter` 曝露這台機器的網路與 CPU counter，Prometheus 每五秒抓一次，Grafana 用 PromQL 查。三個元件都是官方 binary，這門課沒有為它們寫過任何一行程式。PromQL 練習、recording rule 與 alert rule 都在這條路上，而且打在真的網卡上，下載一個大檔案就會讓規則響。

**分析路徑。** Notebook 算完之後用 `to_csv()` 寫檔案、用 `savefig()` 寫圖，兩個都落在 `outputs/workshop/`。一行 `python -m http.server` 把那個資料夾開出來，Grafana 用 Infinity datasource 讀 CSV，用內建的 Text panel 讀 PNG。一樣沒有 exporter，沒有中介服務。

一個月份的歷史分數推不進 Prometheus，因為它是 pull 模型，時間戳來自 scrape 的當下。硬要推就得寫重播器，而重播器會讓時間軸變成假的，在上面做的每一個視窗計算都要先換算一次才能讀。所以歷史結果走檔案，即時指標走 Prometheus。

Notebook 這一端也看得到圖，用的是 matplotlib，跟 `labs/self-study/` 那十份 notebook 同一套寫法，離開這個 repo 也還用得上。兩邊分工：notebook 的圖定住不動，適合逐條比較；dashboard 的 panel 可以互動，適合換條件驗證。兩邊沒有共用的繪圖程式碼，只共用同一批數字，所以兩張圖對不起來就是中間那條路徑斷了。

## 開課前的四個終端機

前三個是安裝好就一直在的服務，第四個要自己開，而且整個下午都不能關。

```bash
brew services start prometheus     # http://localhost:9090
brew services start grafana        # http://localhost:3000
brew services start node_exporter  # http://localhost:9100/metrics

# 在 repo 根目錄，這個視窗留著
python -m http.server 8080 --directory outputs/workshop
```

Prometheus 要讀這個 repo 的設定才會有 recording rule 與 alert rule：

```bash
cp infra/prometheus/prometheus.macos.yml /opt/homebrew/etc/prometheus.yml
cp infra/prometheus/alerts.yml           /opt/homebrew/etc/alerts.yml
curl -X POST http://localhost:9090/-/reload
```

Windows 用 `prometheus.windows.yml`，exporter 是 `windows_exporter`，聽在 9182。

## Grafana 這一端

兩件事，兩件都是官方功能，沒有腳本。

**Datasource。** 需要 Prometheus 和一個 Infinity。Infinity 是 Grafana 外掛目錄裡的簽章外掛，用官方 CLI 裝：

```bash
grafana cli --homepath /opt/homebrew/share/grafana \
  --pluginsDir /opt/homebrew/var/lib/grafana/plugins \
  plugins install yesoreyeram-infinity-datasource
brew services restart grafana
```

兩個 datasource 可以在 Connections > Data sources 手動加，也可以複製 provisioning 檔省下點擊：

```bash
cp infra/grafana/provisioning/datasources.yaml \
   /opt/homebrew/share/grafana/conf/provisioning/datasources/aiops.yaml
brew services restart grafana
```

**Dashboard。** Dashboards > New > Import，貼上 `infra/grafana/dashboards/aiops-workshop.json` 的內容。三列：第一列是 node_exporter 的即時指標，第二列讀 lab CSV，第三列讀 lab PNG。

## 從 Lab 00 開始

Lab 00 要先跑完，它唯一要證明的事是兩條路徑都通。這兩條不通，Lab 01 與 Lab 02 只會得到空的 dashboard。四個服務怎麼起、怎麼在四種壞法之間分辨，都寫在 `00_observability_stack_and_promql.ipynb` 裡。卡住的時候回那份 notebook，不要回這一頁。

## 下午三節

| Lab | 主題 | Notebook |
| --- | --- | --- |
| 00 | 兩條資料路徑與 PromQL。counter 與 rate、`up`、把數字送上 Grafana，故意弄壞再讀出斷在哪 | `00_observability_stack_and_promql.ipynb` |
| 01 | 網路流量 feature engineering。同一段流量對四種 baseline 比較：rolling mean、median 與 MAD、same seasonal position、peer group | `01_network_traffic_feature_engineering.ipynb` |
| 02 | 偵測與告警。偏離量收斂成 score，設門檻得到 label，加上 duration、minimum volume 與 maintenance exclusion 才成為 alert，最後用 scorecard 檢查代價 | `02_anomaly_detection_and_alerting.ipynb` |

Dashboard 只有一張，網址是 <http://localhost:3000/d/aiops-workshop>。三個 lab 寫的是不同檔名的 CSV，彼此不覆蓋，所以跑完 Lab 02 之後 Lab 01 的 panel 還在。

時間範圍要留意。`node_exporter` 的 panel 用相對區間就好，lab CSV 的時間戳落在 2026 年 2 月，要用 Absolute range 才看得到。

順序不能跳。Lab 02 的 evidence panel 畫的是 Lab 01 算出來的 baseline 欄位。

## notebook 裡的 toolkit

每一份 notebook 開頭有一個 toolkit cell，載入、baseline、偵測器、alert policy、事件評估的函式都寫在那裡，直接讀得到也改得動。這門課不把它們收進一個要另外理解的函式庫，`toy_health_indicators_and_phm.ipynb` 就是這個做法的範本：資料科學的邏輯留在 notebook 裡，不藏在 `import` 後面。

四份 notebook 各自帶自己用得到的那部分，所以有些函式會重複出現。這是刻意的取捨：每一份 notebook 都能單獨打開、單獨讀完，不需要先搞懂一個共用套件。畫圖是 notebook 裡的 matplotlib，送資料是 `to_csv()`；toolkit 不畫圖，也不跟 Grafana 說話。

## 這個目錄裡另外兩份 notebook

`toy_health_indicators_and_phm.ipynb` 是二十分鐘的獨立走查，讀同一份 telemetry，但不寫檔案、不碰 Grafana。它處理的是下午三節沒有時間展開的那一段：把多變量偏離收成一個有界的健康指標，再問這個資產的軌跡適不適合外推。第 6 節那個 monotonicity 與 prognosability 的篩選是重點，多數 PHM 展示會跳過它，然後對一個根本不單調的指標做剩餘壽命預測。想接 RUL 的人從那一節開始讀。

`08_agentic_ai_rca_capstone.ipynb` 不屬於下午這三節，時間也排不進去。它接在 Lab 02 的 alert 之後，處理的是「告警發出來以後怎麼查」：把偵測結果整理成 incident context，交給一個在課堂版裡以 deterministic mock 執行的 agent 做 root cause analysis，不需要任何 API token。它跟前三節共用同一份 telemetry，寫出去的是自己的檔名，不會蓋掉前面的畫面。
