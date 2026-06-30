# 安裝 node_exporter

node_exporter 是 Prometheus 的官方 OS metrics 代理人，負責把 CPU、記憶體、網路等系統指標暴露為 Prometheus 格式。工作坊使用它把你的 PC 變成被監控目標。

官方來源：

- node_exporter：[github.com/prometheus/node_exporter](https://github.com/prometheus/node_exporter)
- node_exporter releases：[github.com/prometheus/node_exporter/releases](https://github.com/prometheus/node_exporter/releases)
- Prometheus node_exporter guide：[prometheus.io/docs/guides/node-exporter](https://prometheus.io/docs/guides/node-exporter/)
- windows_exporter：[github.com/prometheus-community/windows_exporter](https://github.com/prometheus-community/windows_exporter)

本指南採用 Prometheus 官方 GitHub release 的 node_exporter binary，下載 URL 使用 `https://github.com/prometheus/node_exporter/releases/download/v<version>/...`。不要把 node_exporter 跟課程的 `infra/rrd_exporter.py` 混在一起：前者讀取你的真實作業系統指標，後者把課程準備好的 network telemetry CSV 轉成 Prometheus 可抓取的 metrics。課程 CSV 是 synthetic data，但它模擬的是整理後的真實網路訊號。

---

## 先確認你的 CPU 架構

```bash
uname -m
```

常見結果：

```text
arm64   Apple Silicon Mac
x86_64  Intel Mac 或多數 Linux PC
```

---

## macOS（官方 release）

到 [node_exporter releases](https://github.com/prometheus/node_exporter/releases) 確認最新版本。以下用 `1.11.1` 作為可直接執行的範例。

Apple Silicon Mac：

```bash
NODE_EXPORTER_VERSION="1.11.1"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.darwin-arm64.tar.gz"
tar xvf "node_exporter-${NODE_EXPORTER_VERSION}.darwin-arm64.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.darwin-arm64/node_exporter" /usr/local/bin/
```

Intel Mac：

```bash
NODE_EXPORTER_VERSION="1.11.1"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.darwin-amd64.tar.gz"
tar xvf "node_exporter-${NODE_EXPORTER_VERSION}.darwin-amd64.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.darwin-amd64/node_exporter" /usr/local/bin/
```

啟動：

```bash
node_exporter
```

看到 `Listening on` 或類似訊息後保持這個終端機開著。另開一個終端機做驗證。

---

## Linux（官方 release）

到 [node_exporter releases](https://github.com/prometheus/node_exporter/releases) 確認最新版本。以下用 `1.11.1` 作為可直接執行的範例。

大多數 x86_64 Linux PC：

```bash
NODE_EXPORTER_VERSION="1.11.1"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
tar xvf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter" /usr/local/bin/
```

ARM64 Linux：

```bash
NODE_EXPORTER_VERSION="1.11.1"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64.tar.gz"
tar xvf "node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64/node_exporter" /usr/local/bin/
```

啟動：

```bash
node_exporter
```

看到 `Listening on` 或類似訊息後保持這個終端機開著。其他發行版服務化方式請參考[官方安裝說明](https://prometheus.io/docs/guides/node-exporter/)。

---

## 驗證 macOS / Linux node_exporter

如果啟動時顯示 `command not found`，改用完整路徑：

```bash
/usr/local/bin/node_exporter
```

另開一個終端機：

```bash
curl -s http://localhost:9100/metrics | head
```

再確認網路指標：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

有輸出表示 node_exporter 正常運行。

如果 `node_exporter` 出現 macOS 安全性阻擋，請到 **System Settings → Privacy & Security** 允許執行。完成後重新啟動 `node_exporter`。

要停止前景執行的 `node_exporter`，回到該終端機按 `Ctrl+C`。

---

## Windows（windows_exporter）

Windows 使用 [windows_exporter](https://github.com/prometheus-community/windows_exporter/releases)。它不是 node_exporter，但在 Windows 上負責同一件事：把 OS metrics 暴露給 Prometheus。

1. 到 Releases 頁面下載最新 `.msi` 安裝檔（例如 `windows_exporter-0.x.x-amd64.msi`）
2. 雙擊安裝，預設 port 是 **9182**（不是 9100）
3. 驗證：在瀏覽器開啟 `http://localhost:9182/metrics`

> 若使用 windows_exporter，Lab 00 的 PromQL 中將 `:9100` 改為 `:9182`，指標名稱前綴為 `windows_net_*` 而非 `node_network_*`。

Prometheus 請使用 Windows 專用設定檔：

```powershell
.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle
```

---

## 設定 Prometheus 抓取 node_exporter

本 repository 的 `prometheus.macos.yml` 和 `prometheus.linux.yml` 都已包含 node_exporter 目標：

```yaml
scrape_configs:
  - job_name: "node-exporter"
    static_configs:
      - targets: ["localhost:9100"]
```

如果 Prometheus 已經依 [02-install-prometheus.md](02-install-prometheus.md) 啟動，安裝 node_exporter 後通常等待幾秒就能看到目標變成 `up`。也可以手動重新載入 Prometheus：

```bash
# macOS / Linux
curl -X POST http://localhost:9090/-/reload
```

```powershell
# Windows
Invoke-WebRequest -Method Post http://localhost:9090/-/reload
```

在 Prometheus UI（`http://localhost:9090`）查詢 `up{job="node-exporter"}` 確認值為 `1`。

Windows 使用 windows_exporter 時，預設 port 是 `9182`，而且指標名稱與 node_exporter 不完全相同。請直接使用 `infra/prometheus/prometheus.windows.yml`，不要修改 macOS / Linux 設定檔。初學者若使用 Windows，建議先完成 self-study 合成資料路徑；若要跑 workshop 即時 OS 指標，依 notebook 提示調整 PromQL 指標名稱。

---

## 確認網路指標可用

在 `http://localhost:9090` 執行以下 PromQL，確認能看到你的網路介面。

**macOS / Linux（node_exporter）：**

```promql
node_network_receive_bytes_total{device!~"lo|docker.*|veth.*"}
```

有結果（macOS 通常看到 `en0`，Linux 通常看到 `eth0` / `ens3` 等）即可進入 `labs/workshop/00_observability_stack_and_promql.ipynb`。

**Windows（windows_exporter）：**

```promql
windows_net_bytes_received_total
```

有結果即可確認 windows_exporter 已被 Prometheus 抓取。
