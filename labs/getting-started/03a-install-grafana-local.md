# 安裝 Grafana 並連接 Prometheus

官方文件：[grafana.com/docs/grafana/latest/setup-grafana/installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)
官方下載頁：[grafana.com/grafana/download](https://grafana.com/grafana/download/)

Grafana 安裝後會在本機建立服務、資料庫與登入設定。本課程的 conda 腳本只處理 Python 環境，不會自動安裝 Grafana。

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

## 連接 Prometheus 為資料來源

1. 左側選單：**Connections → Data sources → Add data source**。
2. 選擇 **Prometheus**。
3. 在 **Prometheus server URL** 填入 `http://localhost:9090`。
4. 點擊 **Save & test**。

出現 "Successfully queried the Prometheus API" 即完成連接。

## 確認整合成功

左側選單 → **Explore**，在 Metrics browser 中輸入 `up`，點擊 **Run query**。回傳資料表示 Grafana 已成功從 Prometheus 讀取指標。

## 匯入課程 Dashboard

本 repository 提供一份 Grafana dashboard JSON：

```text
infra/grafana/dashboards/network_metrics.json
```

匯入方式：

1. 左側選單：**Dashboards → New → Import**。
2. 點擊 **Upload dashboard JSON file**。
3. 選擇 `infra/grafana/dashboards/network_metrics.json`。
4. 如果 Grafana 要求選擇 Prometheus data source，選剛剛建立的 Prometheus。
5. 點擊 **Import**。

匯入後若 panel 沒有資料，先確認 Prometheus 的 `up{job="rrd-exporter"}` 是 `1`，並確認 `python infra/rrd_exporter.py` 的終端機仍在執行。

## 常見問題

**瀏覽器無法開啟 `localhost:3000`？**
確認 Grafana 服務已啟動。macOS 可執行 `brew services list`，Linux 可執行 `systemctl status grafana-server`，Windows 可開啟「服務」管理員查看 `Grafana`。

**Save & test 失敗？**
先確認 Prometheus 可以在 [http://localhost:9090](http://localhost:9090) 開啟。Grafana 的資料來源 URL 應填 `http://localhost:9090`，不是 `http://localhost:3000`。

**Dashboard 沒有資料？**
確認三件事：`python infra/rrd_exporter.py` 正在執行、Prometheus 使用正確作業系統的設定檔啟動、Grafana data source 指向 `http://localhost:9090`。
