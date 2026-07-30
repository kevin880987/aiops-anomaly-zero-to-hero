# AIOps Anomaly Detection: Zero to Hero

## 這門課要解決的問題

一台網路設備每分鐘產生的大量資料無法逐條監控。而要能監控異常，最常見的做法是設定固定門檻，也最常失敗。監控門檻如何設定很依賴工程師經驗。門檻寬鬆，問題會太晚發現；門檻嚴格，則太多 false alarm，接著就開始忽略它們。這門課帶領大家一起從資料驅動的角度，從原始指標算出能解釋的偏離量，再決定多大的偏離值得發出告警。

## 我們要建立的系統

```text
actual OS / network telemetry
  -> node_exporter exposes /metrics
  -> Prometheus stores time-series metrics
  -> the detector service queries Prometheus, scores, exposes /metrics
  -> Prometheus scrapes the score like any other metric
  -> Grafana panels and alert rules read that score with PromQL
```

整條 pipeline 都在地端執行，不需要雲端帳號或伺服器。上面每個元件都是業界在用的官方軟體，只有中間那支偵測服務程式是為了本課程實作方便而寫的。它算完偏離分數之後，把結果送回 Prometheus，當成一般指標存起來拋給 Grafana。這門課會著重於中間的異常偵測演算法。

## 課程產出

一套在地端運作的監控環境。Prometheus、Grafana 與 exporter 都設定完成，並且驗證資料正確。

一支可以完整閱讀、也可以自行修改的偵測服務，以及把它接回 Prometheus 的模組。

一組你自己調過的告警設定，每一個參數都可以驗證，以及在真實系統裡如何維護、調校。

## 適合對象

已能照著指令操作終端機，但第一次接觸 Prometheus 或 Grafana 的維運或後端工程師。想把時間序列資料轉成偵測流程的資料工程師。想要一份教學版範例的讀者。

不預設你有 Kubernetes、雲端平台、Python package 開發或深度學習的經驗。

課程的資料與設定都是為了教學而寫，直接搬進 production 需額外考慮程式設計。

## 開始使用

還沒設定環境的讀者，從 [`labs/getting-started/README.md`](labs/getting-started/README.md) 開始。那份文件會引導安裝順序。

已經有自己環境的讀者，直接執行 [`labs/getting-started/00-check-your-setup.ipynb`](labs/getting-started/00-check-your-setup.ipynb)。它逐格檢查 Python 環境、Prometheus、Grafana Local 與 node_exporter，任何一項失敗都會引導至安裝指南。

課程教材放在 `labs/workshop/`。

## 教材結構

```text
.
├── README.md                  # 本文件
├── environments/              # conda 課程環境，三個平台各一份
├── diagrams/                  # 課程圖表，各章共用同一份，來源在 materials/diagrams/
├── labs/
│   ├── getting-started/       # setup 主入口、互動式檢查 notebook、安裝指南、screenshots/
│   └── workshop/              # 課程教材
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

`data/synthetic/` 底下是標好真實 event 的歷史 CSV，藉此才能設計出幫助辨別 event 並告警的演算法。

## 驗證

本機安裝是否就緒，以 `labs/getting-started/00-check-your-setup.ipynb` 為準。這是唯一建議的檢查入口。


## License

[MIT](LICENSE)
