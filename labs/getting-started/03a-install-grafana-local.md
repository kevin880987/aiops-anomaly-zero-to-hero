# 安裝 Grafana 並連接 Prometheus

官方文件：[安裝說明](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)、[下載頁](https://grafana.com/grafana/download/)

Grafana 負責查詢與畫圖，不自己去抓 exporter。即時指標的資料流是：exporter 曝露 `/metrics`，Prometheus scrape 並儲存時間序列，Grafana 連到 Prometheus 查詢。

工作坊 dashboard 還有第二種資料來源。Notebook 寫出來的 CSV 與 PNG 放在 `outputs/workshop/`，用一行 `python -m http.server` 開啟成 HTTP 服務，Grafana 用 Infinity datasource 直接讀那些檔案。所以本機要安裝兩個 datasource：Prometheus 給即時指標，Infinity 給 lab 結果。

**前置條件：** Prometheus 已安裝並正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

## 安裝 Grafana

**macOS：**

```bash
brew install grafana
brew services start grafana
```

**Linux（Ubuntu / Debian）：**

```bash
sudo apt-get install -y apt-transport-https software-properties-common wget gpg
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
sudo systemctl enable --now grafana-server
```

其他發行版見[官方安裝文件](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)。

**Windows：** 從[下載頁](https://grafana.com/grafana/download/)選 Windows 下載 `.msi` 安裝。服務會自動啟動，沒有的話到「服務」管理員手動啟動 `Grafana`。

安裝完成後開啟 <http://localhost:3000>，帳號密碼都是 `admin`，系統會要求改密碼。

## 安裝 Infinity 外掛

Dashboard 的第二列與第三列讀的是 `outputs/workshop/` 裡的 CSV 與 PNG，走的是 Infinity datasource。它是 Grafana 外掛目錄裡的簽章外掛，用官方 CLI 安裝。

macOS：

```bash
grafana cli --homepath /opt/homebrew/share/grafana \
  --pluginsDir /opt/homebrew/var/lib/grafana/plugins \
  plugins install yesoreyeram-infinity-datasource
brew services restart grafana
```

Intel Mac 的前綴是 `/usr/local`，用 `brew --prefix` 確認。

Linux：

```bash
sudo grafana cli plugins install yesoreyeram-infinity-datasource
sudo systemctl restart grafana-server
```

Windows：在 Grafana 安裝目錄的 `bin` 資料夾執行 `.\grafana.exe cli plugins install yesoreyeram-infinity-datasource`，之後到「服務」管理員重新啟動 `Grafana`。

舊版 Grafana 的指令名稱是 `grafana-cli`，參數相同。

## 建立兩個資料來源

repository 裡有一份 provisioning 檔，複製過去再重啟，兩個 datasource 會一起建立：

```bash
cp infra/grafana/provisioning/datasources.yaml \
   /opt/homebrew/share/grafana/conf/provisioning/datasources/aiops.yaml
brew services restart grafana
```

Linux 的目標路徑是 `/etc/grafana/provisioning/datasources/aiops.yaml`，改完 `sudo systemctl restart grafana-server`。

手動加也可以，在 **Connections → Data sources → Add data source**：Prometheus 的 server URL 填 `http://localhost:9090`，按 **Save & test** 應出現 "Successfully queried the Prometheus API"；Infinity 的名稱取為 `Lab outputs`，其餘留預設。Grafana 是在自己的伺服器端去抓 `http://localhost:8080` 的檔案，所以不需要設定 CORS。

provisioning 檔裡 Prometheus 的 uid 是 `prometheus`，Infinity 的 uid 是 `lab-outputs`，dashboard JSON 就是照這兩個 uid 連過去的。手動建立時名稱可以自己取，匯入 dashboard 時 Grafana 會問你要對應到哪一個。

## 匯入課程 Dashboard

Dashboard 的 JSON 在 `infra/grafana/dashboards/aiops-workshop.json`。在 **Dashboards → New → Import** 貼上 JSON 或上傳檔案，按 **Load**，選好 data source 之後 **Import**。

匯入後在 <http://localhost:3000/d/aiops-workshop>，共三列。第一列是 `node_exporter` 的即時指標，走 Prometheus，左上角的 **Interface** 下拉要選一張真的有流量的網卡。第二列讀 lab CSV，第三列讀 lab PNG，兩列都要求這個終端機開著：

```bash
python -m http.server 8080 --directory outputs/workshop
```

時間範圍要留意。第一列用相對區間就好，第二列與第三列的資料時間戳落在 2026 年 2 月，要切成 Absolute range 才看得到。

## 常見問題

**瀏覽器無法開啟 `localhost:3000`？**
確認 Grafana 服務已啟動。macOS 執行 `brew services list`，Linux 執行 `systemctl status grafana-server`，Windows 開啟「服務」管理員查看 `Grafana`。

**Save & test 失敗？**
先確認 Prometheus 能在 <http://localhost:9090> 開啟。資料來源 URL 應填 `http://localhost:9090`，`3000` 是 Grafana 自己。

**Add data source 裡找不到 Infinity？**
外掛沒有安裝成功，或安裝完沒重啟 Grafana。重新執行一次上面的 `grafana cli plugins install`，macOS 要帶 `--homepath` 與 `--pluginsDir`，否則它會安裝到 Grafana 實際上不會去讀的目錄。

**Dashboard 第一列空白？**
這一列走 Prometheus。查詢 `up{job="node-exporter"}`，值是 `0` 就去啟動 exporter，整筆 job 不存在就是 Prometheus 載錯設定檔，見 [02-install-prometheus.md](02-install-prometheus.md)〈啟動方式的陷阱〉。

**Dashboard 第二列或第三列空白？**
這兩列跟 Prometheus 無關。先在瀏覽器開啟 <http://localhost:8080/>，看得到檔案清單才表示檔案伺服器活著。看得到清單但 panel 還是空的，就是那個 lab 還沒執行完，或是時間範圍沒切到 2026 年 2 月。
