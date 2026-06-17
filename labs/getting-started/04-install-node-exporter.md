# 安裝 node_exporter

node_exporter 是 Prometheus 的官方 OS metrics 代理人，負責把 CPU、記憶體、網路等系統指標暴露為 Prometheus 格式。工作坊使用它把你的 PC 變成被監控目標。

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

## Windows（windows_exporter）

Windows 使用 [windows_exporter](https://github.com/prometheus-community/windows_exporter/releases)，功能等同 node_exporter。

1. 到 Releases 頁面下載最新 `.msi` 安裝檔（例如 `windows_exporter-0.x.x-amd64.msi`）
2. 雙擊安裝，預設 port 是 **9182**（不是 9100）
3. 驗證：在瀏覽器開啟 `http://localhost:9182/metrics`

> 若使用 windows_exporter，Lab 00 的 PromQL 中將 `:9100` 改為 `:9182`，指標名稱前綴為 `windows_net_*` 而非 `node_network_*`。

Prometheus 請使用 Windows 專用設定檔：

```powershell
.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\prometheus\prometheus.windows.yml" --web.enable-lifecycle
```

---

## Linux（apt / 二進制）

**Ubuntu / Debian：**

```bash
# 下載最新版（以 1.8.x 為例）
wget https://github.com/prometheus/node_exporter/releases/download/v1.8.2/node_exporter-1.8.2.linux-amd64.tar.gz
tar xvf node_exporter-1.8.2.linux-amd64.tar.gz
sudo mv node_exporter-1.8.2.linux-amd64/node_exporter /usr/local/bin/

# 執行（前景，測試用）
node_exporter &

# 或設定 systemd service（正式環境）
```

驗證：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

---

## 設定 Prometheus 抓取 node_exporter

本 repository 的 `infra/prometheus/prometheus.yml` 已包含 macOS / Linux 的 node_exporter 目標：

```yaml
scrape_configs:
  - job_name: "node-exporter"
    static_configs:
      - targets: ["localhost:9100"]
```

如果 Prometheus 已經依 [02-install-prometheus.md](02-install-prometheus.md) 啟動，安裝 node_exporter 後通常等待幾秒就能看到目標變成 `up`。也可以手動重新載入 Prometheus：

```bash
curl -X POST http://localhost:9090/-/reload
```

在 Prometheus UI（`http://localhost:9090`）查詢 `up{job="node-exporter"}` 確認值為 `1`。

Windows 使用 windows_exporter 時，預設 port 是 `9182`，而且指標名稱與 node_exporter 不完全相同。請不要改 `infra/prometheus/prometheus.yml`，直接使用 `infra/prometheus/prometheus.windows.yml`。初學者若使用 Windows，建議先完成 self-study 合成資料路徑；若要跑 workshop 即時 OS 指標，依 notebook 提示調整 PromQL 指標名稱。

---

## 確認網路指標可用

在 `http://localhost:9090` 執行以下 PromQL，確認能看到你的網路介面：

```promql
node_network_receive_bytes_total{device!~"lo|docker.*|veth.*"}
```

有結果（至少看到 `en0` 或 `eth0`）即可進入 `labs/workshop/00_observability_stack_and_promql.ipynb`。

Windows 可先查：

```promql
windows_net_bytes_received_total
```

有結果即可確認 windows_exporter 已被 Prometheus 抓取。
