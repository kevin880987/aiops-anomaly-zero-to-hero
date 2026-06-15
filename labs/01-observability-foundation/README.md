# Lab 01: 建立第一個 Network Observability 環境

完成本 lab 後，你可以啟動 Prometheus 與 Grafana、確認 scrape target 正常、執行基本 PromQL，並從 replay data 找出網路介面的流量、錯誤、discard 與已知異常事件。

## 架構

```text
synthetic_rrd_metrics.csv
  -> rrd-exporter replays one timestamp
  -> Prometheus scrapes every 5 seconds
  -> Grafana queries Prometheus
  -> Network Interface Monitoring dashboard
```

預設 `REPLAY_SPEED_X=3600`，因此 30 天 dataset 約 12 分鐘完成一次 replay。資料中的 traffic surge、error burst、discard spike、traffic drop 與 broadcast storm 會在數分鐘內出現。

## 前置需求

安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，並確認：

```bash
docker --version
docker compose version
```

若 `3000`、`8000` 或 `9090` 已被使用，請停止占用該 port 的服務，或修改根目錄 `compose.yaml` 的 host port。

## 操作

在 repository 根目錄執行：

```bash
docker compose up --build -d
docker compose ps
```

等待 `rrd-exporter` 顯示為 healthy，再開啟：

1. <http://localhost:8000/metrics>
2. <http://localhost:9090/targets>
3. <http://localhost:3000>

Grafana 登入資料為 `admin` / `admin`。進入 `AIOps` folder，開啟 `Network Interface Monitoring`。

## 驗證

Prometheus 的 `rrd-exporter` target 應顯示 `UP`。在 Prometheus expression browser 依序執行：

```promql
network_rrd_in_octets
```

```promql
network_rrd_in_errors + network_rrd_out_errors
```

```promql
network_rrd_in_discards + network_rrd_out_discards
```

```promql
network_rrd_event{event_label!="normal"}
```

最後一個 query 在異常事件 replay 到目前時間時會出現值。Grafana 的 `Current Simulated Timestamp` panel 可用來核對目前 replay 位置。

## 調整 replay

以 720× 執行時，完整 dataset 約一小時：

```bash
REPLAY_SPEED_X=720 docker compose up --build -d
```

以 60× 執行時，完整 dataset 約 12 小時：

```bash
REPLAY_SPEED_X=60 docker compose up --build -d
```

修改速度後可執行 `docker compose restart rrd-exporter` 重新開始 replay。

## 練習

1. 找出五個 port 的流量差異。
2. 找到至少一個非 `normal` event，記錄 device、port、event label 與 simulated timestamp。
3. 比較 error burst 與 discard spike 對應的 metrics。
4. 說明為何高流量本身不足以證明介面故障。
5. 保存四個 PromQL query 與一張包含異常事件的 dashboard 截圖。

## 常見問題

查看所有 container logs：

```bash
docker compose logs
```

只查看 replay exporter：

```bash
docker compose logs rrd-exporter
```

重新建立環境：

```bash
docker compose down -v
docker compose up --build -d
```

## 清除

保留 Prometheus 與 Grafana volume：

```bash
docker compose down
```

刪除本 lab 產生的 volume：

```bash
docker compose down -v
```
