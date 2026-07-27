# Getting started

這一頁是課程 setup 的主入口。學員只需要照順序做；安裝細節已拆到各平台或工具自己的文件。

本課程支援 macOS、Linux、Windows。請只執行自己作業系統的指令，不要混用不同 OS 的安裝方式。

---

## 課堂上要準備的東西

課堂用的是 `labs/workshop/`。它需要四個東西同時活著，最後一個要自己在終端機開，而且整個下午都不能關。

| 元件 | 位址 | 這一頁的哪一步 |
| --- | --- | --- |
| Prometheus | <http://localhost:9090> | Step 3 |
| node_exporter（Windows 是 windows_exporter） | <http://localhost:9100/metrics> | Step 4 |
| Grafana | <http://localhost:3000> | Step 5 |
| 檔案伺服器 | <http://localhost:8080> | Step 6 |

前三個是官方 binary，這門課沒有為它們寫過任何一行程式。第四個是 Python 標準函式庫的 `http.server`，把 notebook 寫出來的 CSV 與 PNG 開給 Grafana 讀。

Notebook 本身是自足的：載入、baseline、偵測、評估的函式都寫在每一份 notebook 開頭，不 import 這個 repository 裡的任何模組。上面四個服務是為了讓結果上得了 dashboard，不是 notebook 跑起來的前提。

---

## 0. 先選你的起點

### A. 已經有 Python / conda 環境

直接開啟檢查 notebook：

```text
labs/getting-started/00-check-your-setup.ipynb
```

它會檢查目前 notebook kernel 與 Python packages，然後逐一檢查上面四個服務，並確認 Prometheus 真的抓到了 node_exporter。每個檢查 cell 通過時都會輸出確認訊息。

如果 notebook 顯示缺少任何項目，回到本頁對應步驟補安裝或啟動即可。

### B. 還沒有 Python / conda 環境，或不確定怎麼安裝

從 Step 1 開始做。完成 Step 1 到 Step 6 後，再回來開 `00-check-your-setup.ipynb` 檢查是否全部就緒。

---

## Step 1. 進入 course repo

所有指令都從 `aiops-anomaly-zero-to-hero` 根目錄執行。

macOS / Linux：

```bash
cd /path/to/aiops-anomaly-zero-to-hero
pwd
```

Windows PowerShell：

```powershell
cd C:\path\to\aiops-anomaly-zero-to-hero
Get-Location
```

---

## Step 2. 建立 Python / conda 環境

照這份文件做：[01-setup-python-environment.md](01-setup-python-environment.md)

三個平台共用那一頁，每一步都先列 macOS / Linux 再列 Windows PowerShell。

完成後，確認你能啟用課程環境：

macOS / Linux：

```bash
conda activate aiops-anomaly-zero-to-hero
```

Windows PowerShell：

```powershell
conda activate aiops-anomaly-zero-to-hero
```

接著用你慣用的 notebook 工具開啟 `.ipynb`，VS Code、PyCharm、JupyterLab 或其他支援 Jupyter kernel 的工具都可以。重點是 notebook kernel 要選到 `Python (aiops-anomaly-zero-to-hero)`。

---

## Step 3. 安裝並啟動 Prometheus

照這份文件做：[02-install-prometheus.md](02-install-prometheus.md)

這一步有一個容易踩的坑，那份文件用一整節寫它：Prometheus 必須載到本 repository 的設定檔。用套件管理器的 service 方式啟動，載入的是套件自己的預設設定，裡面沒有 `node-exporter` 這個 job，也沒有 `alerts.yml` 的規則。它不會出錯，只會讓 dashboard 永遠空白。

完成後應能打開 <http://localhost:9090>，並且查得到這一筆：

```promql
up{job="prometheus"}
```

---

## Step 4. 安裝並啟動 node_exporter

照這份文件做：[04-install-node-exporter.md](04-install-node-exporter.md)

macOS / Linux 使用 Prometheus 官方 GitHub release 的 `node_exporter` binary；Windows 使用 `windows_exporter`，它聽在 9182。

工作坊的即時指標、`alerts.yml` 裡的 recording rules 與 alert rules，全部打在這個 exporter 曝露的 `node_network_*` 上。完成後在 Prometheus 查詢：

```promql
up{job="node-exporter"}
```

值應為 `1`。查詢結果裡完全沒有這個 job，表示 Step 3 的設定檔沒有載進去。

---

## Step 5. 安裝 Grafana Local，接上兩個資料來源

照這份文件做：[03a-install-grafana-local.md](03a-install-grafana-local.md)

完成後應能打開 <http://localhost:3000>，並且具備三件事：

1. Prometheus data source 指向 `http://localhost:9090`。
2. Infinity data source（`Lab outputs`），這是外掛，要另外裝。
3. 匯入 `infra/grafana/dashboards/aiops-workshop.json`，dashboard 網址是 <http://localhost:3000/d/aiops-workshop>。

Grafana 自己聽在 `3000`，Prometheus 聽在 `9090`。data source URL 填錯是最常見的失敗。

---

## Step 6. 開一個檔案伺服器

Notebook 算完之後把 CSV 與 PNG 寫進 `outputs/workshop/`，Grafana 用 Infinity datasource 從 HTTP 讀那個資料夾。在 repository 根目錄另開一個終端機：

```bash
python -m http.server 8080 --directory outputs/workshop
```

Windows PowerShell 相同：

```powershell
python -m http.server 8080 --directory outputs\workshop
```

這個視窗整個下午都要開著，關掉就等於 dashboard 第二列與第三列斷線。瀏覽器開 <http://localhost:8080/> 看得到檔案清單即可，剛開始資料夾是空的，那是正常的。

---

## Step 7. 跑 setup check notebook

開啟並逐格執行：

```text
labs/getting-started/00-check-your-setup.ipynb
```

你應該看到四個主要檢查通過：

1. Course repo path 通過。
2. Python kernel / packages 通過。
3. 四個服務都是 `up`。
4. Prometheus 的 `up{job="node-exporter"}` 是 `1`。

如果某一格失敗，notebook 會列出對應安裝指南。先補齊缺項，再重新跑這份 notebook。

請以 notebook 的結果為準。terminal Python、conda environment 與 notebook kernel 三者不一致時，在終端機另跑一支檢查腳本會給出誤判。

---

## Step 8. 開始 labs

從這裡開始：

```text
labs/workshop/00_observability_stack_and_promql.ipynb
```

Lab 00 唯一要證明的事，就是即時指標與分析結果這兩條路徑都通。順序不能跳，Lab 02 的 panel 畫的是 Lab 01 算出來的欄位。四份 notebook 的分工見 [`labs/workshop/README.md`](../workshop/README.md)。

---

## 選用：Grafana Cloud

Grafana Cloud 是選用延伸。課程主線只需要 Grafana Local。

連結：[03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)

---

## 常見錯誤定位

### `conda` 找不到

先重新開一個 terminal。若仍失敗，回到 [01-setup-python-environment.md](01-setup-python-environment.md) 的〈常見問題〉。

### notebook 找不到 `aiops-anomaly-zero-to-hero` kernel

安裝流程中的 kernel 註冊可能被略過。先啟用課程環境，再執行一次：

macOS / Linux：

```bash
conda activate aiops-anomaly-zero-to-hero
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

Windows PowerShell：

```powershell
conda activate aiops-anomaly-zero-to-hero
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

重新載入編輯器的 kernel 選單，再選 `Python (aiops-anomaly-zero-to-hero)`。

### `localhost:9090` 連不上

Prometheus 沒有啟動，或 9090 port 被其他程序佔用。回到 [02-install-prometheus.md](02-install-prometheus.md)。

### `up` 查得到 `job="prometheus"`，查不到 `job="node-exporter"`

Prometheus 載入的是套件的預設設定檔，不是本 repository 的。見 [02-install-prometheus.md](02-install-prometheus.md)〈啟動方式的陷阱〉。

### `localhost:8080` 連不上

Step 6 的檔案伺服器沒開，或啟動後 terminal 被關掉。回到 Step 6 重開一個。

### Grafana `Save & test` 失敗

Grafana data source URL 應填：

```text
http://localhost:9090
```

不要填 `http://localhost:3000`。`3000` 是 Grafana 自己，`9090` 才是 Prometheus。

### Grafana 的 Add data source 裡找不到 Infinity

外掛沒裝，或裝完沒重啟 Grafana。見 [03a-install-grafana-local.md](03a-install-grafana-local.md)〈安裝 Infinity 外掛〉。

---

## Conda environment files

大多數學員不需要手動選這些檔案；請依本 README 的安裝指南建立環境，最後用 `00-check-your-setup.ipynb` 檢查。

| 檔案 | 用途 |
| --- | --- |
| `environments/environment.macos.yml` | macOS 版本 |
| `environments/environment.linux.yml` | Linux 版本 |
| `environments/environment.windows.yml` | Windows 版本 |

三個平台檔都建立同一個 conda environment：`aiops-anomaly-zero-to-hero`。
