# 安裝 Grafana 並連接 Prometheus

官方文件：[grafana.com/docs/grafana/latest/setup-grafana/installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)
官方下載頁：[grafana.com/grafana/download](https://grafana.com/grafana/download/)

Grafana 安裝後會在本機建立服務、資料庫與登入設定。本課程的 Python setup 腳本不會自動安裝它。

**前置條件：** Prometheus 已安裝並正在運作（[02-install-prometheus.md](02-install-prometheus.md)）。

## 安裝 Grafana

### macOS（Homebrew）

```bash
brew install grafana
brew services start grafana
```

### Windows

1. 至 [grafana.com/grafana/download](https://grafana.com/grafana/download/) 選擇 Windows，下載 `.msi` 安裝檔。
2. 執行安裝檔，依指示完成安裝。
3. Grafana 服務會自動啟動。若未啟動，在「服務」管理員中找到 `Grafana` 手動啟動。

### Linux（Ubuntu / Debian）

```bash
sudo apt-get install -y apt-transport-https software-properties-common wget
wget -q -O - https://apt.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

其他發行版請參考官方安裝文件。

## 首次登入

1. 瀏覽器開啟 [http://localhost:3000](http://localhost:3000)。
2. 帳號：`admin`，密碼：`admin`。
3. 系統會要求修改密碼，設定完成後進入主畫面。

## 連接 Prometheus 為資料來源

1. 左側選單：**Connections → Data sources → Add data source**。
2. 選擇 **Prometheus**。
3. 在 **Prometheus server URL** 填入 `http://localhost:9090`。
4. 點擊 **Save & test**。

出現 "Successfully queried the Prometheus API" 即完成連接。

## 確認整合成功

左側選單 → **Explore**，在 Metrics browser 中輸入 `up`，點擊 **Run query**。回傳資料表示 Grafana 已成功從 Prometheus 讀取指標。
