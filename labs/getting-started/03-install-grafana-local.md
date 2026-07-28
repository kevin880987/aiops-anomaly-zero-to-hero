# 安裝 Grafana 並連接 Prometheus

官方文件：[安裝說明](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)、[下載頁](https://grafana.com/grafana/download/)

**前置條件：** Prometheus 已安裝並正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

這一步要安裝 Grafana 與 Infinity 外掛，接上兩個 datasource。

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

## 2. 啟動

在瀏覽器開啟 <http://localhost:3000>，帳號密碼都是 `admin`，系統會要求改密碼。
![alt text](03-grafana-1.png)

## 3. 安裝 Infinity 外掛

在終端機執行，Windows 用 PowerShell。

**macOS：**

```bash
grafana cli --homepath "$(brew --prefix)/share/grafana" \
  --pluginsDir "$(brew --prefix)/var/lib/grafana/plugins" \
  plugins install yesoreyeram-infinity-datasource
brew services restart grafana
```

`$(brew --prefix)` 在 Apple Silicon 是 `/opt/homebrew`，在 Intel Mac 是 `/usr/local`，這行指令兩種都適用。

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
   "$(brew --prefix)/share/grafana/conf/provisioning/datasources/aiops.yaml"
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
$repo = "<你的路徑>\aiops-anomaly-zero-to-hero"
Copy-Item "$repo\infra\grafana\provisioning\datasources.yaml" `
  "C:\Program Files\GrafanaLabs\grafana\conf\provisioning\datasources\aiops.yaml"
Restart-Service Grafana
```

也可以手動新增以下兩個資料源 Prometheus 與 Infinity，在 **Connections → Data sources → Add data source**：Prometheus 的 server URL 填 `http://localhost:9090`，按 **Save & test** 應出現 "Successfully queried the Prometheus API"；Infinity 的名稱取為 `Lab outputs`，其餘留預設。

![alt text](03-grafana-2.png)

## 5. 驗收

確認兩個 datasource。

**Prometheus。** 開 <http://localhost:3000/explore>，datasource 選 `Prometheus`，查詢 `up`，應該回
`job="prometheus"` 值是 `1`。`job="node-exporter"` 這一筆在你完成
[04-install-node-exporter.md](04-install-node-exporter.md) 之前會是 `0` 或不存在，那是正常的。

**Infinity。** `Connections → Data sources → Lab outputs`，頁面能開啟、沒有紅字錯誤即可。這個
這個 datasource 現在還沒有真的資料可以讀，第一次真的查詢要等 Lab 00 建立 dashboard 之後。

## 常見問題

**瀏覽器無法開啟 `localhost:3000`？**
確認服務已啟動。macOS 執行 `brew services list`，Linux 執行 `systemctl status grafana-server`，Windows 在 PowerShell 執行 `Get-Service Grafana`。

**Save & test 失敗？**
先確認 Prometheus 能在 <http://localhost:9090> 開啟。資料來源 URL 應填 `http://localhost:9090`，`3000` 是 Grafana 自己。

**Add data source 裡找不到 Infinity？**
外掛沒有安裝成功，或安裝完沒重啟 Grafana。重新執行一次 `grafana cli plugins install`，macOS 要帶 `--homepath` 與 `--pluginsDir`，否則它會安裝到 Grafana 實際上不會去讀的目錄。

**`up` 這個 query 在 Explore 裡查不到 `node-exporter`？**
整筆 job 不存在就是 Prometheus 載錯設定檔，見 [02-install-prometheus.md](02-install-prometheus.md)〈用 service 啟動〉。dashboard 相關的排查（哪一列空白、CSV 讀取失敗）在
workshop 那份 notebook 自己的〈排查〉一節，這裡還沒有 dashboard 可以排查。
