# 安裝 Grafana 並連接 Prometheus

官方文件：[grafana.com/docs/grafana/latest/setup-grafana/installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)
官方下載頁：[grafana.com/grafana/download](https://grafana.com/grafana/download/)

參考閱讀：

- [普羅米修斯 Prometheus 監控](https://hackmd.io/@cheese-owner/BkF8Kmlc5)

請把 Grafana 理解成視覺化與 dashboard 工具。它不直接取代 Prometheus，也不自己去抓 node_exporter。即時指標的資料流是：exporter 暴露 `/metrics`，Prometheus scrape 並儲存時間序列，Grafana 連到 Prometheus 查詢與畫圖。

工作坊 dashboard 還有第二種資料來源。Notebook 寫出來的 CSV 與 PNG 放在 `outputs/workshop/`，用一行 `python -m http.server` 開出來，Grafana 用 Infinity datasource 直接讀那些檔案。所以本機要裝兩個 datasource：Prometheus 給即時指標，Infinity 給 lab 結果。

Grafana 安裝後會在本機建立服務、資料庫與登入設定。本課程的 Python 環境設定只處理 notebook 需要的套件，不會自動安裝 Grafana。

**前置條件：** Prometheus 已安裝並正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

## 安裝 Grafana

### macOS（Homebrew）

```bash
brew install grafana
brew services start grafana
```

### Linux（Ubuntu / Debian）

```bash
sudo apt-get install -y apt-transport-https software-properties-common wget gpg
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

其他發行版請參考[官方安裝文件](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)。

### Windows

1. 至 [grafana.com/grafana/download](https://grafana.com/grafana/download/) 選擇 Windows，下載 `.msi` 安裝檔。
2. 執行安裝檔，依指示完成安裝。
3. Grafana 服務會自動啟動。若未啟動，在「服務」管理員中找到 `Grafana` 手動啟動。

## 首次登入

1. 瀏覽器開啟 [http://localhost:3000](http://localhost:3000)。
2. 帳號：`admin`，密碼：`admin`。
3. 系統會要求修改密碼，設定完成後進入主畫面。

## 安裝 Infinity 外掛

工作坊 dashboard 的第二列與第三列讀的是 `outputs/workshop/` 裡的 CSV 與 PNG，走的是 Infinity datasource。它是 Grafana 外掛目錄裡的簽章外掛，用官方 CLI 安裝。

macOS（Homebrew）：

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

舊版 Grafana 的指令名稱是 `grafana-cli`，兩者參數相同。

Windows：在 Grafana 安裝目錄的 `bin` 資料夾執行，之後在「服務」管理員重新啟動 `Grafana`：

```powershell
.\grafana.exe cli plugins install yesoreyeram-infinity-datasource
```

## 建立兩個資料來源

兩個都可以在 UI 手動加。

**Prometheus：**

1. 左側選單：**Connections → Data sources → Add data source**。
2. 選擇 **Prometheus**。
3. 在 **Prometheus server URL** 填入 `http://localhost:9090`。
4. 點擊 **Save & test**。

出現 "Successfully queried the Prometheus API" 即完成連接。

**Infinity：** 同樣在 **Add data source** 選 **Infinity**，名稱改成 `Lab outputs`，其餘留預設，按 **Save & test**。Grafana 是在自己的伺服器端去抓 `http://localhost:8080` 的檔案，所以不需要設定 CORS。

不想手動點的話，repository 裡有一份 provisioning 檔，複製過去再重啟 Grafana，兩個 datasource 會一起建立：

```bash
cp infra/grafana/provisioning/datasources.yaml \
   /opt/homebrew/share/grafana/conf/provisioning/datasources/aiops.yaml
brew services restart grafana
```

Linux 的目標路徑是 `/etc/grafana/provisioning/datasources/aiops.yaml`，改完 `sudo systemctl restart grafana-server`。這份檔案裡 Prometheus 的 uid 是 `prometheus`，Infinity 的 uid 是 `lab-outputs`，dashboard JSON 就是照這兩個 uid 連過去的；手動建立時名稱可以自己取，匯入 dashboard 時 Grafana 會問你要對應到哪一個。

## 確認整合成功

左側選單 → **Explore**，datasource 選 Prometheus，在 Metrics browser 中輸入 `up`，點擊 **Run query**。回傳資料表示 Grafana 已成功從 Prometheus 讀取指標。

## 匯入課程 Dashboard

課程 dashboard 的 JSON 在 `infra/grafana/dashboards/aiops-workshop.json`。

1. 左側選單：**Dashboards → New → Import**。
2. 貼上 JSON 內容，或點 **Upload dashboard JSON file** 選檔案。
3. 點 **Load**，若 Grafana 要求選擇 data source，選前一節建立的 Prometheus 與 Infinity。
4. 點擊 **Import**。

Dashboard 匯入後在 `http://localhost:3000/d/aiops-workshop`，共三列。第一列是 `node_exporter` 的即時指標，走 Prometheus；左上角的 **Interface** 下拉要選一張真的有流量的網卡。第二列讀 lab CSV，第三列讀 lab PNG，兩列都要求這個終端機開著：

```bash
python -m http.server 8080 --directory outputs/workshop
```

時間範圍要留意。第一列用相對區間就好，第二列與第三列的資料時間戳落在 2026 年 2 月，要切成 Absolute range 才看得到。

## 常見問題

**瀏覽器無法開啟 `localhost:3000`？**
確認 Grafana 服務已啟動。macOS 可執行 `brew services list`，Linux 可執行 `systemctl status grafana-server`，Windows 可開啟「服務」管理員查看 `Grafana`。

**Save & test 失敗？**
先確認 Prometheus 可以在 [http://localhost:9090](http://localhost:9090) 開啟。Grafana 的資料來源 URL 應填 `http://localhost:9090`，不是 `http://localhost:3000`。

**Add data source 裡找不到 Infinity？**
外掛沒裝成功，或裝完沒重啟 Grafana。重跑一次上面的 `grafana cli plugins install`，注意 macOS 要帶 `--homepath` 與 `--pluginsDir`，否則它會裝到 Grafana 實際上不會去讀的目錄。

**Dashboard 第一列空白？**
這一列走 Prometheus。查 `up{job="node-exporter"}`，值是 `0` 就去啟動 exporter，整筆 job 不存在就是 Prometheus 載錯設定檔，見 [02-install-prometheus.md](02-install-prometheus.md)〈啟動方式的陷阱〉。

**Dashboard 第二列或第三列空白？**
這兩列跟 Prometheus 無關。先在瀏覽器開 `http://localhost:8080/`，看得到檔案清單才表示檔案伺服器活著；看得到清單但 panel 還是空的，就是那個 lab 還沒跑完，或是時間範圍沒切到 2026 年 2 月。
