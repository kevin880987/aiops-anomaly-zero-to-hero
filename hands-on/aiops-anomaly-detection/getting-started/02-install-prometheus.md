# 安裝 Prometheus

官方文件：[prometheus.io/docs/prometheus/latest/installation](https://prometheus.io/docs/prometheus/latest/installation/)
官方下載頁：[prometheus.io/download](https://prometheus.io/download/)

Prometheus 是系統級監控服務，安裝方式依作業系統與權限設定而異。本課程的 Python setup 腳本不會自動安裝它。

## macOS（Homebrew）

```bash
brew install prometheus
```

安裝後以預設設定啟動：

```bash
prometheus --config.file=/opt/homebrew/etc/prometheus.yml
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## Windows

1. 至 [prometheus.io/download](https://prometheus.io/download/) 下載 `prometheus-*windows-amd64.zip`。
2. 解壓縮到任意目錄，例如 `C:\prometheus`。
3. 在該目錄執行：

```powershell
.\prometheus.exe --config.file=prometheus.yml
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## Linux（Ubuntu / Debian）

```bash
sudo apt-get update && sudo apt-get install -y prometheus
sudo systemctl start prometheus
sudo systemctl enable prometheus
```

其他發行版請參考官方安裝文件。

## 確認安裝成功

瀏覽器開啟 [http://localhost:9090](http://localhost:9090)，在 Expression 欄位輸入 `up`，點擊 **Execute**。回傳結果中看到任何一筆 `value="1"` 即表示 Prometheus 正在收集資料。

## 下一步

安裝完成後，繼續 [03-install-grafana.md](03-install-grafana.md)。
