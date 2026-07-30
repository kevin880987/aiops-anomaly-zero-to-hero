# Getting started

這門課的重點是異常偵測的演算法設計。Grafana 與 dashboard 是拿來看資料與驗證結果的工具。

課程 setup 的主入口，照順序做。安裝細節在各步驟連到的文件裡。

本課程支援 macOS、Linux、Windows。

最後我們會執行 `00-check-your-setup.ipynb` 確認所有需要的安裝。

## 課堂上要維持執行的四個服務

課堂用的是 `labs/workshop/`。這四個服務要同時執行。

| 元件 | 位址 | 步驟 |
| --- | --- | --- |
| Prometheus | <http://localhost:9090> | Step 3 |
| node_exporter（Windows 是 windows_exporter） | <http://localhost:9100/metrics> | Step 4 |
| Grafana | <http://localhost:3000> | Step 5 |
| `detector.py` | <http://localhost:9200/metrics> | Lab 00 第 4 節 |

前三個是官方 binary，在這一章先完成安裝。第四個是這門課唯一自己寫的服務，Lab 00 會在課堂上啟動它。

## Step 1. 進入教材根目錄

所有指令都從教材根目錄執行，也就是同時包含 `environments/`、`labs/`、`infra/` 的那一層。

```bash
cd <你放教材的位置>/aiops-anomaly-zero-to-hero
```

Windows PowerShell 是 `cd C:\Users\<你的帳號>\aiops-anomaly-zero-to-hero`。

## Step 2. 建立 Python / conda 環境

照 [01-setup-python-environment.md](01-setup-python-environment.md) 做，三個平台共用那一頁。

驗收：`conda activate aiops-anomaly-zero-to-hero` 能啟用環境，且你慣用的 notebook 工具在 kernel 選單中列得出它。

## Step 3. 安裝並啟動 Prometheus

照 [02-install-prometheus.md](02-install-prometheus.md) 做。那份文件用一整節說明這一步唯一的失敗模式：Prometheus 必須載入教材裡的設定檔，否則它照常執行、照常回答查詢，只是永遠 scrape 不到 node_exporter。

驗收：<http://localhost:9090> 能開啟，`up{job="prometheus"}` 查詢得到值。

## Step 4. 安裝並啟動 node_exporter

照 [04-install-node-exporter.md](04-install-node-exporter.md) 做。Windows 用的是 windows_exporter，listening port 為 9182。

工作坊的即時指標與 `alerts.yml` 的所有規則都打在這個 exporter 曝露的 `node_network_*` 上。

驗收：`up{job="node-exporter"}` 是 `1`。查詢結果裡完全沒有這個 job，表示 Step 3 的設定檔沒有載進去。

## Step 5. 安裝 Grafana Local，接上資料來源

照 [03-install-grafana-local.md](03-install-grafana-local.md) 做。這門課的 datasource 只有
Prometheus 一個。

驗收：`Connections → Data sources` 列得出 `Prometheus`，Save & test 顯示成功。URL 填成 `3000` 是最
常見的失敗，`3000` 是 Grafana 自己。dashboard 在 Lab 00 逐格建立，這裡不驗收。

## Step 6. 執行 setup check notebook

逐格執行 `00-check-your-setup.ipynb`，四格都要通過：教材根目錄、Python 環境、Prometheus 與 Grafana 與 node_exporter、準備完成。

某一格失敗時，它會列出對應的安裝指南。補齊之後重新執行整份。

請以這份 notebook 的結果為準。terminal Python、conda environment 與 notebook kernel 三者不一致時，在終端機另外執行一支檢查腳本會給出誤判。

## Step 7. 開始 labs

```text
labs/workshop/
```

從這個資料夾裡編號最小的那一份 notebook 開始。Lab 00 建立完整的 pipeline，從網卡的 counter 一路到
觸發的告警，中間的偵測環節是自己寫的 Python 服務。建立完成之後的每一節都只處理演算法。編號就是順序，不能
跳，後一節的分數建立在前一節的 baseline 上。各單元的分工寫在那個資料夾自己的說明裡。

## 選用：Grafana Cloud

課程主線只需要 Grafana Local。把指標推上雲端的做法在
`03b-setup-grafana-cloud.md`，這份文件放在教材外層的工作目錄，不隨教材一起發布。
