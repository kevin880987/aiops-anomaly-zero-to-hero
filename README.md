# AIOps Anomaly Detection: Zero to Hero

## 這門課要解決的問題

一台網路設備每分鐘產生的指標，比任何人能逐條檢視的都多。安裝好 Grafana、把圖畫出來，這一步完成的是呈現。沒有人盯著螢幕的那些時段，系統得自己說出哪一段不對勁。

最常見的做法是設定固定門檻，也最常失敗。門檻寬鬆，半夜的異常沒有人知道；門檻嚴格，值班的人一週收到上百封通知，接著開始忽略它們。這門課處理的就是中間那一段：怎麼從原始指標算出能解釋的偏離量，再決定多大的偏離值得叫醒一個人。

## 你要建立的系統

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> the detector service queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

整條 pipeline 都在你自己的機器上執行，不需要雲端帳號，也不需要另一台伺服器。上面每個元件都是業界在用的官方軟體，只有中間那支偵測服務是課程自己寫的。

它算完偏離分數之後，把結果送回 Prometheus，當成一般指標存起來。多繞這一步，Grafana 與告警規則查詢這個分數的方式，就跟查詢任何一個現成指標完全相同，沒有一段需要知道它是 Python 算出來的。

好處要到改良演算法的時候才顯現。偵測邏輯可以整個換掉，dashboard 與告警規則一行都不必改。真實系統上線也是這個順序，先讓 pipeline 穩定，再迭代模型。

## 課程產出

一套在自己機器上運作的監控環境。Prometheus、Grafana 與 exporter 都設定完成，而且驗證過資料真的有進來。

一支可以完整閱讀、也可以自行修改的偵測服務，以及把它接回 Prometheus 的做法。

一組你自己調過的告警設定，每一個參數都說得出為什麼是這個值、用什麼數字驗證過，以及在真實系統裡它該由哪一層維護。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師。想把時間序列資料轉成偵測流程的資料工程師。想要一份教學版範例的讀者。

不預設你有 Kubernetes、雲端平台、Python package 開發或深度學習的經驗。Grafana Cloud 是選用延伸。

課程的資料與設定都是為了教學而寫，直接搬進 production 並不合適。

## 開始使用

還沒設定環境的讀者，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始。那份文件給的是安裝順序，以及每一步過關的條件。

已經有自己環境的讀者，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)。它逐格檢查教材根目錄、Python 環境、Prometheus、Grafana Local 與 node_exporter，任何一格失敗都會指出該補哪一份安裝指南。

課程教材放在 `labs/workshop/`，依課程進度分批發布，上到那幾節才會發到你手上。

## 教材結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── diagrams/                  # 課程圖表，各章共用同一份，來源在 materials/diagrams/
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南、screenshots/
│   └── workshop/              # 課程教材，依課程進度分批發布
├── data/
│   ├── synthetic/             # 可重建的 organized network telemetry CSV
│   └── sample/                # 原始 LibreNMS/RRDTool sample data（選讀）
├── outputs/
│   └── workshop/              # 課程產出，不隨教材發布
└── infra/
    ├── prometheus/            # 三個平台的 scrape 設定，以及 recording / alert rules
    └── grafana/
        ├── provisioning/      # datasource 的 YAML，用 Grafana 內建的 file provisioning
        └── dashboards/        # 示範用的 dashboard JSON，匯入即可看到即時資料
```

課程用兩種資料。走 Prometheus 的那一種是這台機器此刻的流量，真實，但沒有真值可以對照。`data/synthetic/` 底下是標好真值的歷史 CSV，那是真實營運資料整理過後的樣子，有真值才能量出 baseline 的好壞。

## 驗證

本機是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口。在終端機另外執行檢查腳本會給出誤判，因為 command-line Python 與 notebook kernel 不一定是同一個環境。

Prometheus 的設定檔用 `promtool` 檢查：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

## License

[MIT](LICENSE)
