# 設定 Grafana Cloud 並連接 Prometheus

官方文件：[grafana.com/docs/grafana-cloud/send-data/metrics/metrics-prometheus](https://grafana.com/docs/grafana-cloud/send-data/metrics/metrics-prometheus/)

本步驟為選用延伸，需要先完成 [03a-install-grafana-local.md](03a-install-grafana-local.md)。設定完成後，指標會同時出現在本機 Grafana Local（`http://localhost:3000`）與 Grafana Cloud（雲端 UI）兩個地方。

Prometheus 在本機執行並透過 `remote_write` 推送指標到 Grafana Cloud 免費方案（free tier）；你在 Grafana Cloud 網頁 UI 中查看，不需要在本機安裝額外的 Grafana 服務。

**前置條件：** Grafana Local 已設定完成（[03a-install-grafana-local.md](03a-install-grafana-local.md)）且 Prometheus 正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

---

## 步驟 1 — 建立 Grafana Cloud 免費帳號

前往 [grafana.com/auth/sign-up](https://grafana.com/auth/sign-up)，選 **Get started free**，完成帳號建立。

建立後系統會引導你建立一個 **stack**（例如 `yourname.grafana.net`）。記下這個網址，後面會用到。

---

## 步驟 2 — 取得 Prometheus remote_write 憑證

1. 登入 [grafana.com/profile/org](https://grafana.com/profile/org)（My Account）。
2. 左側選單 → **My Stacks**，點擊你的 stack。
3. 在 **Prometheus** 欄位點擊 **Details**。
4. 記下以下兩個值：
   - **Remote Write Endpoint**（格式：`https://prometheus-prod-XX-prod-XX-X.grafana.net/api/prom/push`）
   - **Username / Instance ID**（一串數字）

---

## 步驟 3 — 建立 API Token

1. 在同一個 stack 詳細頁面，點擊 **Generate now**（或進入 **Access Policies → Create access policy**）。
2. 勾選 **metrics:write** 權限。
3. 按 **Create**，複製產生的 token（只會顯示一次）。

---

## 步驟 4 — 填入 prometheus.macos.yml 的 remote_write

開啟 `infra/prometheus/prometheus.macos.yml`（Windows 用 `prometheus.windows.yml`），找到 `remote_write` 區塊，將佔位符替換為你的實際值：

```yaml
remote_write:
  - url: https://prometheus-prod-XX-prod-XX-X.grafana.net/api/prom/push
    basic_auth:
      username: 123456          # 你的 Username / Instance ID
      password: glc_xxxxx...    # 你的 API token
```

存檔。

---

## 步驟 5 — 重啟 Prometheus

關閉正在執行的 Prometheus 程序，用相同指令重新啟動：

```bash
# macOS / Linux（在 repository 根目錄）
prometheus --config.file=infra/prometheus/prometheus.macos.yml --web.enable-lifecycle
```

```powershell
# Windows
.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle
```

啟動後等待約 15 秒，讓第一批指標推送出去。

---

## 步驟 6 — 確認指標已到達 Grafana Cloud

1. 開啟你的 Grafana Cloud 網址（`https://yourname.grafana.net`）。
2. 左側選單 → **Explore**。
3. 資料來源選 **Prometheus**（Grafana Cloud 已預先設定）。
4. 在 Metrics browser 輸入 `up`，點擊 **Run query**。

看到 `up{job="rrd-exporter"}` 值為 `1` 即表示 remote_write 設定正確。

---

## 步驟 7 — 匯入課程 Dashboard

本 repository 提供一份 Grafana dashboard JSON：

```text
infra/grafana/dashboards/network_metrics.json
```

匯入方式：

1. 左側選單 → **Dashboards → New → Import**。
2. 點擊 **Upload dashboard JSON file**，選擇 `infra/grafana/dashboards/network_metrics.json`。
3. 在 **Prometheus** 欄位選擇 Grafana Cloud 預設的 Prometheus datasource。
4. 點擊 **Import**。

匯入後若 panel 顯示 `No data`，先確認 `up{job="rrd-exporter"}` 在 Explore 中值為 `1`。

---

## 常見問題

**Explore 查不到任何指標？**
確認 prometheus.macos.yml 的 remote_write url、username、password 都已填入正確值，且 Prometheus 在修改後已重啟。等待 30 秒再試。

**remote_write url 格式不對？**
URL 一定要以 `/api/prom/push` 結尾。從 My Account → Stack → Prometheus Details 頁面複製，不要手動拼接。

**token 只顯示一次，我沒複製到？**
回到 My Account → Stack → Prometheus Details → Access Policies，建立一個新 token。

**Dashboard panel 一直 `No data`，但 `up` 可以查到？**
確認 exporter 正在執行（`python infra/rrd_exporter.py`）。Dashboard 使用的指標是 `network_rrd_*`，這些指標由 exporter 提供。
