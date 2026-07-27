# Getting started

課程 setup 的主入口，照順序做。安裝細節在各步驟連到的文件裡，這一頁只給順序與每一步的驗收條件。

本課程支援 macOS、Linux、Windows。只執行自己作業系統的指令。

已經有 conda 環境的話，可以直接開 `00-check-your-setup.ipynb`，它會告訴你缺哪一項，再回到對應步驟補。

## 課堂上要準備的東西

課堂用的是 `labs/workshop/`。它需要四個東西同時活著，最後一個要自己在終端機開，而且整個下午都不能關。

| 元件 | 位址 | 步驟 |
| --- | --- | --- |
| Prometheus | <http://localhost:9090> | Step 3 |
| node_exporter（Windows 是 windows_exporter） | <http://localhost:9100/metrics> | Step 4 |
| Grafana | <http://localhost:3000> | Step 5 |
| 檔案伺服器 | <http://localhost:8080> | Step 6 |

前三個是官方 binary。第四個是 Python 標準函式庫的 `http.server`，把 notebook 寫出來的 CSV 與 PNG 開給 Grafana 讀。

上面四個服務是為了讓結果上得了 dashboard，不是 notebook 執行起來的前提。

## Step 1. 進入 course repo

所有指令都從 repository 根目錄執行。

```bash
cd /path/to/aiops-anomaly-zero-to-hero
```

Windows PowerShell 用 `cd C:\path\to\aiops-anomaly-zero-to-hero`。

## Step 2. 建立 Python / conda 環境

照 [01-setup-python-environment.md](01-setup-python-environment.md) 做，三個平台共用那一頁。

驗收：`conda activate aiops-anomaly-zero-to-hero` 能啟用環境，而且你慣用的 notebook 工具在 kernel 選單裡看得到它。

## Step 3. 安裝並啟動 Prometheus

照 [02-install-prometheus.md](02-install-prometheus.md) 做。那份文件用一整節寫這一步唯一的坑：Prometheus 必須載到本 repository 的設定檔，否則它照樣活著、照樣回答查詢，只是永遠抓不到 node_exporter。

驗收：<http://localhost:9090> 打得開，`up{job="prometheus"}` 查詢得到值。

## Step 4. 安裝並啟動 node_exporter

照 [04-install-node-exporter.md](04-install-node-exporter.md) 做。Windows 用的是 windows_exporter，listening port 為 9182。

工作坊的即時指標與 `alerts.yml` 的所有規則都打在這個 exporter 曝露的 `node_network_*` 上。

驗收：`up{job="node-exporter"}` 是 `1`。查詢結果裡完全沒有這個 job，表示 Step 3 的設定檔沒有載進去。

## Step 5. 安裝 Grafana Local，接上兩個資料來源

照 [03a-install-grafana-local.md](03a-install-grafana-local.md) 做。Infinity 是外掛，要另外安裝。

驗收：<http://localhost:3000/d/aiops-workshop> 打得開，Prometheus data source 指向 `http://localhost:9090`。填成 `3000` 是最常見的失敗，`3000` 是 Grafana 自己。

## Step 6. 開一個檔案伺服器

Notebook 算完之後把 CSV 與 PNG 寫進 `outputs/workshop/`，Grafana 用 Infinity datasource 從 HTTP 讀那個資料夾。在 repository 根目錄另開一個終端機：

```bash
python -m http.server 8080 --directory outputs/workshop
```

Windows PowerShell 的路徑是 `outputs\workshop`。

這個視窗整個下午都要開著，關掉就等於 dashboard 第二列與第三列斷線。

驗收：<http://localhost:8080/> 看得到檔案清單。剛開始資料夾是空的，那是正常的。

## Step 7. 執行 setup check notebook

逐格執行 `00-check-your-setup.ipynb`，四格都要通過：repo 路徑、Python 環境、Prometheus 與 Grafana 與 node_exporter、準備完成。

某一格失敗時，它會列出對應的安裝指南。補齊之後重新執行整份。

請以這份 notebook 的結果為準。terminal Python、conda environment 與 notebook kernel 三者不一致時，在終端機另外執行一支檢查腳本會給出誤判。

## Step 8. 開始 labs

```text
labs/workshop/00_observability_stack_and_promql.ipynb
```

Lab 00 唯一要證明的事，就是即時指標與分析結果這兩條路徑都通。順序不能跳，Lab 02 的 panel 畫的是 Lab 01 算出來的欄位。四份 notebook 的分工見 [`labs/workshop/README.md`](../workshop/README.md)。

## 選用：Grafana Cloud

課程主線只需要 Grafana Local。想把指標推上雲端再看 [03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)。
