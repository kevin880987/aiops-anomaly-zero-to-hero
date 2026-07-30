# AIOps Anomaly Detection: Zero to Hero

這門課走一遍營運監控的完整資料流，而且整條線在你自己的機器上真的會運作。OS 產生 telemetry，exporter 曝露 `/metrics`，Prometheus scrape 並儲存時間序列。接著課程自己寫的一支偵測服務回頭查 Prometheus、算出偏離分數、把分數曝露成 `/metrics`，於是 Prometheus 把它當成一般指標抓回去，Grafana 與告警規則查詢的就是那個分數。

這門課把時間花在演算法上，畫面只用來確認演算法的輸出。Lab 00 一次建立完整的 pipeline，之後每一節處理的都是這個分數的計算方式。

每個方法都要能解釋它為什麼被選、用什麼數字驗證，以及在真實系統裡該放在哪一層。不需要雲端帳號，Grafana Cloud 是選用延伸。

教材按課程進度分批發布，你手上這一批不是全部。之後排到的單元會補進 `labs/workshop/`，那個資料夾的內容會隨梯次變多，實際有哪幾份以你收到的教材為準；RCA capstone 與自學路線在後續梯次發布。

## 開始使用

還沒設定環境的讀者，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始，它給的是順序與每一步的驗收條件。

已經有自己環境的讀者，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)，它會檢查教材根目錄、Python 環境、Prometheus、Grafana Local 與 node_exporter。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師；想把時間序列資料轉成偵測流程的資料工程師；想要一份可以完整閱讀、也可以自行修改的教學版範例資料的讀者。這門課的資料與設定都是為了教學而寫，直接搬進 production 並不合適。

不預設有 Kubernetes、雲端平台、Python package 開發或深度學習經驗。

## 學習成果

先把 telemetry 到 alert 的 pipeline 接通，確認每一段真的有資料流過，再回頭反覆改良算分數的那一段。每次改良都要拿得出數字來支持。

你會啟動本機的 Prometheus、Grafana Local 與 node_exporter，並確認資料真的被抓取。你會用 PromQL 查詢 counter、rate、label filtering 與 aggregation，從 raw network counters 建立可解釋的 time-series features，再比較不同的 baseline。偏離量彙整成分數之後，以門檻判定成 label，套上 policy 才送得出 alert。這組設定值不值得上線，由 event recall、detection delay 與 alerts per day 決定。Python 算出來的分數會送回 Prometheus，讓 Grafana 與 alert rules 以查詢一般指標的方式取用。每一份 notebook 開頭都寫了那一節自己的目標。

## 教材路線

環境設定完成之後，第一節把整條 pipeline 接通，之後的每一節都在同一條 pipeline 上改良算分數的那一段。

Lab 00 讀的是這台機器此刻的流量，走 Prometheus。凡是要評演算法好壞的單元，讀的都是 `data/synthetic/` 底下標好真值的歷史 CSV，因為沒有答案就量不出好壞，那些單元全程用 matplotlib 畫圖。在歷史資料上挑出來的 baseline 與政策，就是要放進 Lab 00 那支服務裡的演算法。

## Labs

工作坊的 notebook 都在 `labs/workshop/`，同一個資料夾裡還有 `detector.py`，那是這門課唯一自己寫的服務，六十行上下，可以完整閱讀，也可以直接修改。它算分數的那個函式正是每一節要換掉的部分，其餘的程式碼不會再改動。各節分別處理哪一段、要花多久，寫在那個資料夾自己的說明裡。

Grafana 端全部走官方功能。datasource 用內建的檔案 provisioning（`infra/grafana/provisioning/datasources.yaml`）接上 Prometheus，這一步在環境設定就做完。Dashboard 在工作坊那一批逐格建立，一張 panel 畫原始速率，一張畫算出來的分數，第三張畫告警現在的狀態。`infra/grafana/dashboards/aiops-workshop.json` 是另外一份示範用的 dashboard，panel 不同，匯入之後就能看到這台機器此刻的資料，用來確認 Prometheus 與 Grafana 之間確實接通了。告警規則寫在 `infra/prometheus/alerts.yml`，隨時可以用一次下載讓它響。

## 資料流

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> detector.py queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

分數繞回 Prometheus 之後，下游沒有任何一段知道它是 Python 算的，所以上線的時候換掉的是演算法，pipeline 原封不動。

拿歷史資料評分的單元另外讀 `data/synthetic/` 底下的 synthetic CSV，那是真實營運資料整理過後的樣子：五個 port、一整個月、十八個標好的事件。有真值才量得出一個 baseline 好不好，這台機器此刻的流量沒有真值可比。

## 設計地圖

notebook 裡調的每個參數在真實系統裡都有對應的位置，而那個位置決定了上線之後由誰維護它。

scrape interval 與 label 設計落在 Prometheus 的 scrape config。rate、ratio、rolling window、lag 與多解析度這類特徵落在 recording rules，或是另外一支 feature service。閾值、baseline 視窗、deadband、duration 與誤報預算落在 alert rules 與 Alertmanager。至於哪一段計算該留在 PromQL、哪一段該進到偵測服務裡，那是每一節都會再問一次的問題。

每一份 notebook 在動到參數的地方，會指出它在生產環境的對應位置。

## 自我檢核

| 階段 | 檢核問題 |
| --- | --- |
| 環境設定 | `00-check-your-setup.ipynb` 四格是否全部通過 |
| Observability | Prometheus 的 `up` 對 node_exporter 與 aiops-detector 兩個 job 是否都是 1 |
| Feature engineering | 算出來的欄位是否能一路追溯回 raw counters |
| Detection | 每種 anomaly flag 是否有明確 threshold 或 score 解釋 |
| Alerting | alert 是否被合理聚合，是否犧牲了需要立即處理的訊號 |
| Deployment | 換掉偵測服務裡的演算法之後，dashboard 與 alert rules 是否不用改也能跟著變 |

## 驗證指令

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口，可避免 command-line script 與 notebook kernel 使用不同 Python 環境而造成誤判。

Prometheus 設定用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

`alerts.yml` 的規則打在自己這台機器上，所以隨時可以驗證。下載一個大檔案，`TrafficAnomaly` 會依序經過 Normal、Pending 與 Firing。

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

工作坊 notebook 是自足的，載入、baseline、偵測、評估的函式就寫在每一份 notebook 開頭的 toolkit cell 裡，可以直接閱讀，也可以直接修改，不必先理解另一個函式庫。

## License

[MIT](LICENSE)
