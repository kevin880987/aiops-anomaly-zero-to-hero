# 安裝 Grafana 並連接 Prometheus

官方文件：[安裝說明](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)、[下載頁](https://grafana.com/grafana/download/)

**前置條件：** Prometheus 已安裝並正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

這一步要安裝 Grafana 與 Infinity 外掛，接上兩個 datasource，匯入一份 dashboard。

## 1. 安裝 Grafana

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

**Windows：** 從[下載頁](https://grafana.com/grafana/download/)選 Windows 下載 `.msi` 安裝。服務會自動啟動，沒有的話在系統管理員權限的 PowerShell 執行 `Start-Service Grafana`。

## 3. 啟動
開啟 <http://localhost:3000>，帳號密碼都是 `admin`，系統會要求改密碼。
![alt text](03a-grafana-1.png)

## 3. 安裝 Infinity 外掛

在終端機執行，Windows 用 PowerShell。

**macOS：**

```bash
grafana cli --homepath /opt/homebrew/share/grafana \
  --pluginsDir /opt/homebrew/var/lib/grafana/plugins \
  plugins install yesoreyeram-infinity-datasource
brew services restart grafana
```

Intel Mac 的前綴是 `/usr/local`，用 `brew --prefix` 確認。

**Linux：**

```bash
sudo grafana cli plugins install yesoreyeram-infinity-datasource
sudo systemctl restart grafana-server
```

**Windows：** 在 PowerShell 執行，路徑換成自己的 Grafana 安裝目錄：

```powershell
cd "C:\Program Files\GrafanaLabs\grafana\bin"
.\grafana.exe cli plugins install yesoreyeram-infinity-datasource
Restart-Service Grafana
```

`Restart-Service` 要用系統管理員權限開啟的 PowerShell，一般權限開的視窗會回權限錯誤。

舊版 Grafana 的指令名稱是 `grafana-cli`，參數相同。

## 4. 建立兩個資料來源

複製 provisioning 檔再重新啟動，兩個 datasource 會一起建立。

**macOS：**

```bash
cp infra/grafana/provisioning/datasources.yaml \
   /opt/homebrew/share/grafana/conf/provisioning/datasources/aiops.yaml
brew services restart grafana
```

**Linux：**

```bash
sudo cp infra/grafana/provisioning/datasources.yaml \
   /etc/grafana/provisioning/datasources/aiops.yaml
sudo systemctl restart grafana-server
```

**Windows：** 在 PowerShell 執行，`$repo` 換成自己 clone 的位置：

```powershell
$repo = "C:\Users\<你的帳號>\aiops-anomaly-zero-to-hero"
Copy-Item "$repo\infra\grafana\provisioning\datasources.yaml" `
  "C:\Program Files\GrafanaLabs\grafana\conf\provisioning\datasources\aiops.yaml"
Restart-Service Grafana
```

手動加也可以，在 **Connections → Data sources → Add data source**：Prometheus 的 server URL 填 `http://localhost:9090`，按 **Save & test** 應出現 "Successfully queried the Prometheus API"；Infinity 的名稱取為 `Lab outputs`，其餘留預設。

## 5. 匯入 dashboard

在 **Dashboards → New → Import** 貼上 `infra/grafana/dashboards/aiops-workshop.json` 的內容或上傳檔案，按 **Load**，選好 data source 之後 **Import**。

## 6. 驗收

<http://localhost:3000/d/aiops-workshop> 能開啟，第一列有即時曲線。左上角的 **Interface** 下拉要選一張真的有流量的網卡。

第二列與第三列需要這個終端機維持執行，才讀取得到 lab 結果：

```bash
python -m http.server 8080 --directory outputs/workshop
```

時間範圍要留意。第一列用相對區間就好，第二列與第三列的資料時間戳落在 2026 年 2 月，要切成 Absolute range 才顯示得出來。

## Dashboard 的兩種資料來源

Grafana 負責查詢與畫圖，不自己去抓 exporter。第一列的即時指標走 Prometheus：exporter 曝露 `/metrics`，Prometheus scrape 並儲存時間序列，Grafana 連過去查詢。

第二列與第三列走檔案。Notebook 寫出來的 CSV 與 PNG 放在 `outputs/workshop/`，用一行 `python -m http.server` 開啟成 HTTP 服務，Infinity datasource 直接讀那些檔案。Grafana 是在自己的伺服器端去抓 `http://localhost:8080`，所以不需要設定 CORS。

provisioning 檔裡 Prometheus 的 uid 是 `prometheus`，Infinity 的 uid 是 `lab-outputs`，dashboard JSON 就是照這兩個 uid 連過去的。手動建立時名稱可以自己取，匯入時 Grafana 會問你要對應到哪一個。

## 常見問題

**瀏覽器無法開啟 `localhost:3000`？**
確認服務已啟動。macOS 執行 `brew services list`，Linux 執行 `systemctl status grafana-server`，Windows 在 PowerShell 執行 `Get-Service Grafana`。

**Save & test 失敗？**
先確認 Prometheus 能在 <http://localhost:9090> 開啟。資料來源 URL 應填 `http://localhost:9090`，`3000` 是 Grafana 自己。

**Add data source 裡找不到 Infinity？**
外掛沒有安裝成功，或安裝完沒重啟 Grafana。重新執行一次 `grafana cli plugins install`，macOS 要帶 `--homepath` 與 `--pluginsDir`，否則它會安裝到 Grafana 實際上不會去讀的目錄。

**Dashboard 第一列空白？**
這一列走 Prometheus。查詢 `up{job="node-exporter"}`，值是 `0` 就去啟動 exporter，整筆 job 不存在就是 Prometheus 載錯設定檔，見 [02-install-prometheus.md](02-install-prometheus.md)〈用 service 啟動〉。

**Dashboard 第二列或第三列空白？**
這兩列跟 Prometheus 無關。先在瀏覽器開啟 <http://localhost:8080/>，列得出檔案清單才表示檔案伺服器仍在執行。清單正常但 panel 仍是空的，就是那個 lab 還沒執行完，或是時間範圍沒切到 2026 年 2 月。
