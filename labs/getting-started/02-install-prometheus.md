# 啟動課程 exporter，安裝並啟動 Prometheus

官方文件：[prometheus.io/docs/prometheus/latest/installation](https://prometheus.io/docs/prometheus/latest/installation/)
官方下載頁：[prometheus.io/download](https://prometheus.io/download/)

Prometheus 是系統級監控服務，安裝方式依作業系統與權限設定而異。本課程的 conda 腳本只處理 Python 環境，不會自動安裝 Prometheus。

本課程提供兩份 Prometheus 設定檔。請依作業系統選一份使用：

```text
infra/prometheus/prometheus.yml          macOS / Linux，使用 node_exporter :9100
infra/prometheus/prometheus.windows.yml  Windows，使用 windows_exporter :9182
```

macOS / Linux 設定檔會抓取三個本機目標：

```text
localhost:9090  Prometheus 自己
localhost:8000  課程 exporter.py
localhost:9100  node_exporter（工作坊短版需要）
```

Windows 設定檔會抓取：

```text
localhost:9090  Prometheus 自己
localhost:8000  課程 exporter.py
localhost:9182  windows_exporter
```

先完成 [01a](01a-setup-macos-python-environment.md)、[01b](01b-setup-linux-python-environment.md) 或 [01c](01c-setup-windows-python-environment.md)，確認 conda 環境已建立。

## 先啟動課程 exporter

開啟第一個終端機，回到 repository 根目錄後執行：

```bash
conda activate aiops-anomaly-zero-to-hero
python infra/exporter.py
```

看到 `Exporting metrics on http://localhost:8000/metrics` 後保持這個終端機開著。另開一個終端機繼續安裝與啟動 Prometheus。

驗證 exporter：

```bash
curl http://localhost:8000/metrics
```

Windows PowerShell 可用：

```powershell
Invoke-WebRequest http://localhost:8000/metrics
```

## macOS（Homebrew）

```bash
brew install prometheus
```

安裝後開啟第二個終端機，回到 repository 根目錄，使用本課程提供的設定檔啟動：

```bash
prometheus --config.file=infra/prometheus/prometheus.yml --web.enable-lifecycle
```

如果終端機顯示 `prometheus: command not found`，先確認 Homebrew 的 `bin` 目錄已加入 `PATH`：

```bash
brew --prefix
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## Linux（二進制）

```bash
PROM_VERSION="3.12.0"
curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
tar xvf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
cd "prometheus-${PROM_VERSION}.linux-amd64"
./prometheus --config.file=/path/to/aiops-anomaly-zero-to-hero/infra/prometheus/prometheus.yml --web.enable-lifecycle
```

請先到 [prometheus.io/download](https://prometheus.io/download/) 確認目前最新版本，再更新 `PROM_VERSION`。也可以使用發行版套件管理器安裝，但版本可能落後官方 release。

若你的系統已透過套件管理器安裝 `prometheus` 指令，也可以在 repository 根目錄執行：

```bash
prometheus --config.file=infra/prometheus/prometheus.yml --web.enable-lifecycle
```

其他發行版請參考[官方安裝文件](https://prometheus.io/docs/prometheus/latest/installation/)。

## Windows

1. 至 [prometheus.io/download](https://prometheus.io/download/) 下載 `prometheus-*windows-amd64.zip`。
2. 解壓縮到任意目錄，例如 `C:\prometheus`。
3. 開啟第二個 PowerShell，在 Prometheus 解壓縮目錄執行：

```powershell
.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## 確認安裝成功

瀏覽器開啟 [http://localhost:9090](http://localhost:9090)，在 Expression 欄位輸入 `up`，點擊 **Execute**。回傳結果中看到任何一筆 `value="1"` 即表示 Prometheus 正在收集資料。

建議逐一查詢：

```promql
up{job="prometheus"}
up{job="csv-exporter"}
```

若你已完成 node_exporter 或 windows_exporter 安裝，也查詢對應項目：

```promql
up{job="node-exporter"}
```

```promql
up{job="windows-exporter"}
```

Prometheus、csv-exporter 與你的 OS exporter 都回傳 `1` 表示設定正確。若 OS exporter 尚未安裝，這個目標會暫時是 `0` 或不存在，完成 [04-install-node-exporter.md](04-install-node-exporter.md) 後再確認即可。

## 常見問題

**瀏覽器無法開啟 `localhost:9090`？**
確認 Prometheus 指令視窗仍在執行中。若看到 `address already in use`，表示 9090 連接埠已被占用，請先關閉舊的 Prometheus 程序。

**macOS 顯示 `brew: command not found`？**
請先安裝 Homebrew：[https://brew.sh](https://brew.sh)，或改用 Prometheus 官方下載頁的 binary 安裝方式。

## 下一步

Prometheus 本機安裝完成後，選擇一條 Grafana 路徑：

- **路徑 A — 本機 Grafana：** → [03a-install-grafana-local.md](03a-install-grafana-local.md)（安裝本機 Grafana，資料來源設為 `http://localhost:9090`）
- **路徑 B — Grafana Cloud：** → [03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)（建立免費帳號，設定 remote_write 推送指標）

兩條路徑可以看到的 dashboard 與 PromQL 查詢完全相同。

工作坊短版也需要 node_exporter，可以同步完成 [04-install-node-exporter.md](04-install-node-exporter.md)。
