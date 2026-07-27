# 設定 Grafana Cloud 並連接 Prometheus

官方文件：[Prometheus metrics on Grafana Cloud](https://grafana.com/docs/grafana-cloud/send-data/metrics/metrics-prometheus/)

選用延伸。設定完成後，指標會同時出現在本機 Grafana Local 與 Grafana Cloud 的網頁 UI。做法是本機 Prometheus 透過 `remote_write` 把指標推送到 Grafana Cloud 免費方案，雲端那一側不需要再安裝任何東西。

**前置條件：** Grafana Local 已設定完成（[03a-install-grafana-local.md](03a-install-grafana-local.md)），Prometheus 正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

## 1. 建立帳號與取得憑證

到 [grafana.com/auth/sign-up](https://grafana.com/auth/sign-up) 選 **Get started free** 建立帳號。系統會引導你建立一個 stack，例如 `yourname.grafana.net`，記下這個網址。

登入 [My Account](https://grafana.com/profile/org) → **My Stacks** → 點你的 stack → **Prometheus** 欄位的 **Details**，記下兩個值：

- **Remote Write Endpoint**，格式是 `https://prometheus-prod-XX-prod-XX-X.grafana.net/api/prom/push`
- **Username / Instance ID**，一串數字

同一頁點 **Generate now**（或進入 **Access Policies → Create access policy**），勾選 **metrics:write**，按 **Create** 複製產生的 token。它只顯示一次。

## 2. 填入設定檔並重啟

開啟 `infra/prometheus/prometheus.macos.yml`（Windows 用 `prometheus.windows.yml`），找到 `remote_write` 區塊填入實際值：

```yaml
remote_write:
  - url: https://prometheus-prod-XX-prod-XX-X.grafana.net/api/prom/push
    basic_auth:
      username: 123456          # 你的 Username / Instance ID
      password: glc_xxxxx...    # 你的 API token
```

存檔，關閉正在執行的 Prometheus，用相同指令重新啟動，等約 15 秒讓第一批指標推送出去。

## 3. 確認指標已到達

開啟你的 Grafana Cloud 網址 → **Explore** → 資料來源選 **Prometheus**（Grafana Cloud 已預先設定）→ 在 Metrics browser 查詢 `up`。

看到 `up{job="node-exporter"}` 值為 `1` 就表示 remote_write 設定正確。

## 4. 匯入課程 Dashboard

在 **Dashboards → New → Import** 上傳 `infra/grafana/dashboards/aiops-workshop.json`，**Prometheus** 欄位選 Grafana Cloud 預設的 datasource。

第一列的即時指標走 Prometheus，會跟著 remote_write 上雲。第二列與第三列讀本機檔案伺服器上的 lab 結果，Grafana Cloud 連不到 `localhost:8080`，所以那兩列只在 Grafana Local 有資料。

## 常見問題

**Explore 查詢不到任何指標？**
確認設定檔的 remote_write url、username、password 都已填入正確值，且 Prometheus 在修改後已重啟。等 30 秒再試。

**remote_write url 格式不對？**
URL 一定要以 `/api/prom/push` 結尾。從 Prometheus Details 頁面複製，不要手動拼接。

**token 只顯示一次，沒複製到？**
回到 Prometheus Details → Access Policies，建立一個新 token。

**第一列 panel 一直 `No data`，但 `up` 查詢得到？**
第一列用的是 `node_network_*`，由 node_exporter 提供。確認它正在執行，見 [04-install-node-exporter.md](04-install-node-exporter.md)。
