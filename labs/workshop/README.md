# 工作坊下午場：從 telemetry 到 alert

上午把 anomaly 定義成在脈絡下相對於一條明確 baseline 的偏離。下午把這個定義變成可以執行的步驟：你會親手選 baseline、算 score、把 score 收成 label、讓 label 通過 policy 變成 alert，最後用 event-level recall 與 alerts per day 去評這套設定值不值得帶進值班室。

## 兩條資料路徑

下午的每一個數字都會出現在 Grafana 上，走的是兩條不同的路。分開的理由是儲存模型。

**即時路徑。** `node_exporter` 曝露這台機器的網路與 CPU counter，Prometheus 每 5 秒抓一次，Grafana 用 PromQL 查詢。三個元件都是官方 binary，這門課沒有為它們寫過任何一行程式。PromQL 練習、recording rule 與 alert rule 都在這條路上，而且打在真的網卡上，下載一個大檔案就會讓規則響。

**分析路徑。** Notebook 算完之後用 `to_csv()` 寫檔案、用 `savefig()` 寫圖，兩個都落在 `outputs/workshop/`。一行 `python -m http.server` 把那個資料夾開出來，Grafana 用 Infinity datasource 讀 CSV，用內建的 Text panel 讀 PNG。一樣沒有 exporter，沒有中介服務。

兩條路徑與它們在 Grafana 上的對應，見 [`diagrams/lab00_observability_stack_arch.svg`](diagrams/lab00_observability_stack_arch.svg)。

一整個月的歷史分數不容易進 Prometheus，因為它是 pull 模型，時間戳來自 scrape 的當下。`promtool tsdb create-blocks-from openmetrics` 做得到，時間戳也保得住，但一整個月會產生數百個 block，還要搬進 data 目錄重啟，每次重新執行 notebook 都得再來一次。所以課堂上歷史結果走檔案，即時指標走 Prometheus。

Infinity 在這裡是課堂用的替身。真實系統裡這些分數由服務算完曝露在 `/metrics`，跟其他指標一樣被 scrape。所以 dashboard 刻意讓 Grafana 這一側維持相同形態：欄位名是 `aiops_*` 的 metric 名，port 用 dashboard 變數篩選，對應 PromQL 的 label selector。上線時換掉 datasource，面板不動。

Notebook 這一端也繪製同一批數字，用的是 matplotlib，離開這個 repo 也還用得上。notebook 的圖定住不動，適合逐條比較；dashboard 的 panel 可以互動，適合換條件驗證。兩邊沒有共用的繪圖程式碼，只共用同一批數字，所以兩張圖對不起來就是中間那條路徑斷了。

## 開課前要維持執行的四個終端機

前三個是安裝完成後常駐的服務，第四個要自己啟動並維持執行。

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

**Datasource。** 需要 Prometheus 與 Infinity 兩個。Infinity 是 Grafana 外掛目錄裡的簽章外掛，用官方 CLI 安裝：

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

**Dashboard。** 這門課的 dashboard 不匯入，一格一格自己建：第一列在 Lab 00 建，讀
node_exporter 的即時指標；第二列從 Lab 01 開始建，讀各 lab 寫出的 CSV；第三列讀 lab 的 PNG。
每個 lab 的 notebook 裡有那一段的完整建法。`infra/grafana/dashboards/aiops-workshop.json`
是建完之後的答案卷，卡住時核對某張 panel 的設定用，不要在這裡整份匯入。

## 從 Lab 00 開始

Lab 00 要先執行完，它要確認的是兩條路徑都通。這兩條不通，Lab 01 與 Lab 02 只會得到空的 dashboard。四個服務怎麼起、怎麼在四種壞法之間分辨，都寫在 `00_observability_stack_and_promql.ipynb` 裡。排查時回那份 notebook，不要回這一頁。

## 下午三節

| Lab | 主題 | Notebook |
| --- | --- | --- |
| 00 | 兩條資料路徑與 PromQL。counter 與 rate、`up`、把數字送上 Grafana，故意弄壞再讀出斷在哪 | `00_observability_stack_and_promql.ipynb` |
| 01 | 網路流量 feature engineering。同一段流量對四種 baseline 比較：rolling mean、median 與 MAD、same seasonal position、peer group | `01_network_traffic_feature_engineering.ipynb` |
| 02 | 偵測與告警。偏離量收斂成 score，設門檻得到 label，加上 duration、minimum volume 與 maintenance exclusion 才成為 alert，最後用 scorecard 檢查代價 | `02_anomaly_detection_and_alerting.ipynb` |

四種偵測方法的取捨見 [`diagrams/lab02_detection_methods.svg`](diagrams/lab02_detection_methods.svg)。

Dashboard 只有一張，是自己建的那份。三個 lab 寫的是不同檔名的 CSV，彼此不覆蓋，所以執行完 Lab 02 之後 Lab 01 的 panel 還在。

時間範圍要留意。`node_exporter` 的 panel 用相對區間就好，lab CSV 的時間戳落在 2026 年 2 月，要用 Absolute range 才顯示得出來。

順序不能跳。Lab 02 的 evidence panel 畫的是 Lab 01 算出來的 baseline 欄位。

## notebook 裡的 toolkit

每一份 notebook 開頭有 toolkit cell，載入、baseline、偵測器、alert policy、事件評估的函式都寫在那裡，可以直接閱讀與修改。這門課不把它們收進要另外理解的函式庫，資料科學的邏輯留在 notebook 裡，不藏在 `import` 後面。

三份 notebook 各自帶自己需要的函式，所以有些函式會重複出現。重複是為了讓每一份 notebook 都能單獨開啟、單獨讀完，不需要先理解一個共用套件。畫圖是 notebook 裡的 matplotlib，送資料是 `to_csv()`；toolkit 不畫圖，也不跟 Grafana 說話。
