# 安裝 node_exporter

官方來源：[Prometheus 官方 guide](https://prometheus.io/docs/guides/node-exporter/)、[node_exporter](https://github.com/prometheus/node_exporter/releases)、[windows_exporter](https://github.com/prometheus-community/windows_exporter)

node_exporter 把這台機器的 CPU、記憶體、網路指標曝露成 Prometheus 格式，讓你的 PC 成為被監控目標。三份 Prometheus 設定檔預設就帶它的 job，`infra/prometheus/alerts.yml` 的 recording rules 與 alert rules 也全部打在 `node_network_*` 上，所以沒有它，工作坊 dashboard 第一列與所有規則都不會有值。

它讀的是真實作業系統指標，跟 notebook 讀的 `data/synthetic/synthetic_rrd_metrics.csv` 是兩回事。後者是 synthetic data，模擬的是整理後的真實網路訊號。

## macOS

在終端機執行，架構（Apple Silicon 或 Intel）由指令自己判斷：

```bash
VERSION="1.11.1"
PLATFORM="darwin-arm64"; [ "$(uname -m)" = "x86_64" ] && PLATFORM="darwin-amd64"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.${PLATFORM}.tar.gz"
tar xvf "node_exporter-${VERSION}.${PLATFORM}.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${VERSION}.${PLATFORM}/node_exporter" /usr/local/bin/
node_exporter
```

看到 `Listening on` 之後保持這個終端機執行，另外開啟一個做驗證：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

有輸出就表示它正常運作。要停止前景執行的 node_exporter，回到該終端機按 `Ctrl+C`。

啟動時顯示 `command not found` 就改用完整路徑 `/usr/local/bin/node_exporter`。出現安全性阻擋時，到 **System Settings → Privacy & Security** 允許執行，再重新啟動。

## Linux

在終端機執行，架構由指令自己判斷：

```bash
VERSION="1.11.1"
PLATFORM="linux-amd64"; [ "$(uname -m)" = "aarch64" ] && PLATFORM="linux-arm64"
curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.${PLATFORM}.tar.gz"
tar xvf "node_exporter-${VERSION}.${PLATFORM}.tar.gz"
sudo mkdir -p /usr/local/bin
sudo mv "node_exporter-${VERSION}.${PLATFORM}/node_exporter" /usr/local/bin/
node_exporter
```

看到 `Listening on` 之後保持這個終端機執行，另外開啟一個做驗證：

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -5
```

有輸出就表示它正常運作。要停止前景執行的 node_exporter，回到該終端機按 `Ctrl+C`。

啟動時顯示 `command not found` 就改用完整路徑 `/usr/local/bin/node_exporter`。要當成服務常駐執行，見[官方 guide](https://prometheus.io/docs/guides/node-exporter/)。

## Windows

Windows 用的是 [windows_exporter](https://github.com/prometheus-community/windows_exporter/releases)，在 Windows 上負責同一件事。

1. 從 Releases 頁面下載最新的 `.msi`（例如 `windows_exporter-0.x.x-amd64.msi`）。
2. 雙擊安裝。預設 port 是 **9182**，不是 9100。
3. 瀏覽器開啟 <http://localhost:9182/metrics> 驗證。

Windows 的指標名稱前綴是 `windows_net_*` 而不是 `node_network_*`，Prometheus 請直接使用 `infra/prometheus/prometheus.windows.yml`（在 repository 根目錄執行），不要修改 macOS / Linux 設定檔。`alerts.yml` 的規則寫的是 node_exporter 的指標名稱，在 Windows 上不會有值；工作坊 dashboard 第一列的兩張 panel 與 Lab 00 的 PromQL 同理，要自己換成 `windows_net_bytes_received_total` 這一組。

## 讓 Prometheus 抓到它

設定檔裡本來就有這個 job：

```yaml
scrape_configs:
  - job_name: "node-exporter"
    static_configs:
      - targets: ["localhost:9100"]
```

Prometheus 已經依 [02-install-prometheus.md](02-install-prometheus.md) 啟動的話，安裝完等幾秒 target 就會變成 `up`。要立刻生效就重新載入：

```bash
curl -X POST http://localhost:9090/-/reload
```

Windows PowerShell 是 `Invoke-WebRequest -Method Post http://localhost:9090/-/reload`。回 `405` 表示啟動時沒有帶 `--web.enable-lifecycle`，處理方式見 [02-install-prometheus.md](02-install-prometheus.md)，直接重啟 Prometheus 也有同樣效果。

## 確認網路指標可用

在 <http://localhost:9090> 查詢：

```promql
node_network_receive_bytes_total{device!~"lo|docker.*|veth.*"}
```

macOS 通常看到 `en0`，Linux 通常是 `eth0` 或 `ens3`。Windows 改為查詢 `windows_net_bytes_received_total`。有結果就可以進入 `labs/workshop/00_observability_stack_and_promql.ipynb`。

## 規則檔看的是哪一張網卡

`up{job="node-exporter"}` 是 `1`，但 `net:traffic_bps` 查詢不到值，通常是這裡的問題：`alerts.yml` 的 recording rules 只認 `device=~"en0|eth0"` 這兩個名字。

1. 查自己這台實際在傳資料的網卡：

   ```promql
   topk(3, rate(node_network_receive_bytes_total[5m]))
   ```

2. 前三名裡有 `en0` 或 `eth0` 就不用改，這一節結束。沒有的話（Linux 常見 `enp3s0`、`ens33` 這類名字），把 `alerts.yml` 裡的 `device=~"en0|eth0"` 換成查到的那個名字，存檔後重新載入 Prometheus（見上面〈讓 Prometheus 抓到它〉）。
