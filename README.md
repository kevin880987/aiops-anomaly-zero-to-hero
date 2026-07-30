# AIOps Anomaly Detection: Zero to Hero

這門課從網卡的 counter 開始，一路接到告警，中間每一段都在你自己的機器上執行。node_exporter 把作業系統的 telemetry 曝露成 `/metrics`，Prometheus 每 5 秒抓一次，存成時間序列。接著課程自己寫的一支偵測服務回頭查 Prometheus，算出偏離分數並取名 `aiops_traffic_score`，再把它曝露成 `/metrics`，於是 Prometheus 把它當成一般指標抓回去。Grafana 的 panel 與告警規則查詢的都是這個偏離分數。

偏離分數繞回 Prometheus 之後，下游沒有任何一段知道它是 Python 算的。這個做法決定了後面每一節的形狀：改良演算法不必動 pipeline，所以課程的時間花在演算法上，畫面只用來確認演算法的輸出。

## 開始使用

還沒設定環境的讀者，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始。那份文件給的是安裝順序，以及每一步過關的條件。

已經有自己環境的讀者，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)。它逐格檢查教材根目錄、Python 環境、Prometheus、Grafana Local 與 node_exporter，任何一格失敗都會指出該補哪一份安裝指南。

教材按課程進度分批發布，你手上這一批不是全部。之後排到的單元會補進 `labs/workshop/`，那個資料夾的內容會隨梯次變多；RCA capstone 與自學路線在後續梯次發布。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師。想把時間序列資料轉成偵測流程的資料工程師。想要一份可以完整閱讀、也可以自行修改的教學版範例的讀者。

不預設你有 Kubernetes、雲端平台、Python package 開發或深度學習的經驗，也不需要任何雲端帳號。Grafana Cloud 是選用延伸。

課程的資料與設定都是為了教學而寫，直接搬進 production 並不合適。

## 這條 pipeline

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> detector.py queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

上面只有 `labs/workshop/detector.py` 是課程自己寫的，一百行上下，可以完整閱讀，也可以直接修改。其餘每個元件都是官方軟體。Lab 00 一次建立完整的 pipeline，之後每一節換掉的都是 `detector.py` 裡算偏離分數的那個函式，其他程式碼不會再改動。

告警規則寫在 `infra/prometheus/alerts.yml`。規則的條件來自哪裡，從寫法上看不出來。`ErrorRateSurge` 的條件由 PromQL 算，`TrafficAnomaly` 的條件用 Python 算出來的偏離分數，兩條的寫法完全一樣。把偏離分數送回 Prometheus，換到的就是這種一致性。

Grafana 端全部走官方功能。datasource 用內建的檔案 provisioning（`infra/grafana/provisioning/datasources.yaml`）接上 Prometheus，這一步在環境設定就做完。三張 panel 在工作坊那一批逐格建立，一張畫原始速率，一張畫偏離分數，第三張畫告警現在的狀態。`infra/grafana/dashboards/aiops-workshop.json` 是另外一份示範用的 dashboard，panel 不同，匯入之後就能看到這台機器此刻的資料。

## 兩種資料

Lab 00 讀的是這台機器此刻的流量，走 Prometheus。這份資料真實，但沒有真值可以對照，量不出一個 baseline 好不好。

要評演算法好壞的單元需要真值，所以改讀 `data/synthetic/` 底下的 CSV。五個 port、一整個月、十個標好的事件，其中兩個同時打在所有 port 上，展開成十八段有標記的時窗。那份資料是真實營運資料整理過後的樣子。這些單元全程用 matplotlib 畫圖，產出留在 notebook 裡，定住的圖適合逐條比較。在它上面挑出來的 baseline 與政策，最後要放回 `detector.py`。

## 學習成果

先把 telemetry 到 alert 的 pipeline 接通，確認每一段真的有資料流過，再回頭反覆改良算偏離分數的那一段。每次改良都要拿得出數字來支持。

你會啟動本機的 Prometheus、Grafana Local 與 node_exporter，並確認資料真的被抓取。你會用 PromQL 查詢 counter、rate、label filtering 與 aggregation，從 raw network counters 建立可解釋的 time-series features，再比較不同的 baseline。偏離量先彙整成偏離分數，再以門檻判定成 label，套上 policy 才送得出 alert。這組設定值不值得上線，由 event recall、detection delay 與 alerts per day 決定。

每個方法都要說得出它為什麼被選、用什麼數字驗證，以及在真實系統裡該放在哪一層。

## 參數在生產環境的位置

notebook 裡調的每個參數在真實系統裡都有對應的位置，而那個位置決定了上線之後由誰維護它。

scrape interval 與 label 設計落在 Prometheus 的 scrape config。rate、ratio、rolling window、lag 與多解析度這類特徵落在 recording rules，或是另外一支 feature service。閾值、baseline 視窗、deadband、duration 與誤報預算落在 alert rules 與 Alertmanager。至於哪一段計算該留在 PromQL、哪一段該進到偵測服務裡，那是每一節都會再問一次的問題。

## 教材結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── diagrams/                  # 課程圖表，各章共用同一份，來源在 materials/diagrams/
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南、screenshots/
│   └── workshop/              # 工作坊 notebooks、detector.py
├── data/
│   ├── synthetic/             # 可重建的 organized network telemetry CSV
│   └── sample/                # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/
│   └── workshop/              # Labs 產出，不隨教材發布
└── infra/
    ├── prometheus/            # 三個平台的 scrape 設定，以及 recording / alert rules
    └── grafana/
        ├── provisioning/      # datasource 的 YAML，用 Grafana 內建的 file provisioning
        └── dashboards/        # 示範用的 dashboard JSON，匯入即可看到即時資料
```

工作坊 notebook 是自足的。載入、baseline、偵測、評估的函式都寫在每一份 notebook 開頭的 toolkit cell 裡，可以直接閱讀，也可以直接修改，不必先理解另一個函式庫。

## 驗證

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口。在終端機另外執行檢查腳本會給出誤判，因為 command-line Python 與 notebook kernel 不一定是同一個環境。

Prometheus 的設定檔用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

`alerts.yml` 的規則打在自己這台機器上，所以隨時可以驗證。偵測服務啟動之後下載一個大檔案，`TrafficAnomaly` 會依序經過 Normal、Pending 與 Firing。

## License

[MIT](LICENSE)
