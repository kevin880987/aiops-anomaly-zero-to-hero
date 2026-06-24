# 安裝 node_exporter

node_exporter 是 Prometheus 的官方 OS metrics 代理人，負責把 CPU、記憶體、網路等系統指標暴露為 Prometheus 格式。工作坊使用它把你的 PC 變成被監控目標。

官方來源：

- node_exporter：[github.com/prometheus/node_exporter](https://github.com/prometheus/node_exporter)
- Prometheus node_exporter guide：[prometheus.io/docs/guides/node-exporter](https://prometheus.io/docs/guides/node-exporter/)
- windows_exporter：[github.com/prometheus-community/windows_exporter](https://github.com/prometheus-community/windows_exporter)

---

## macOS（Homebrew）

```bash
brew install node_exporter
brew services start node_exporter
```

驗證：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

有輸出表示正常運行。

停止服務：

```bash
brew services stop node_exporter
```

---

## Linux（二進制）

到 [github.com/prometheus/node_exporter/releases](https://github.com/prometheus/node_exporter/releases) 下載最新版（取 `linux-amd64`）。以下使用 `<VERSION>` 作為佔位符，請用 release 頁面目前最新版本取代：

```bash
NODE_EXPORTER_VERSION="1.11.1"
wget "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
tar xvf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter" /usr/local/bin/

# 前景執行（測試用）
node_exporter &
```

驗證：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

有輸出表示正常運行。其他發行版請參考[官方安裝說明](https://prometheus.io/docs/guides/node-exporter/)。

---

## Windows（windows_exporter）

Windows 使用 [windows_exporter](https://github.com/prometheus-community/windows_exporter/releases)，功能等同 node_exporter。

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
