# 安裝並啟動 Prometheus

官方文件：[prometheus.io/docs/prometheus/latest/installation](https://prometheus.io/docs/prometheus/latest/installation/)
官方下載頁：[prometheus.io/download](https://prometheus.io/download/)

參考閱讀：

- [普羅米修斯 Prometheus 監控](https://hackmd.io/@cheese-owner/BkF8Kmlc5)
- [DevOps 課程 Prometheus 1](https://wade-software-study-note.medium.com/devops%E8%AA%B2%E7%A8%8B-prometheus-1-7a690f7d4426)

這兩篇文章的重點是 Prometheus 的 pull model、target、metric、exporter 與 Grafana data source。本課程沿用這個學習順序，但不照抄舊版 binary 與 Raspberry Pi 路徑。請以本頁指令、repository 內的 `infra/prometheus/*.yml`，以及官方下載頁為準。

Prometheus 是系統級監控服務，安裝方式依作業系統與權限設定而異。本課程的 Python 環境設定只處理 notebook 需要的套件，不會自動安裝 Prometheus。

## 這門課的 Prometheus 抓什麼

這門課只有兩個 scrape target：Prometheus 自己，以及 `node_exporter`（Windows 上是 `windows_exporter`）。兩個都是官方 binary，這門課沒有為它們寫過任何一行程式。

Notebook 算出來的結果不經過 Prometheus。它用 `to_csv()` 與 `savefig()` 寫進 `outputs/workshop/`，一行 `python -m http.server` 把資料夾開出來，Grafana 端用 Infinity datasource 讀檔案。分開的理由是儲存模型。Prometheus 是 pull 模型，時間戳來自 scrape 的當下，一個月份的歷史分數推不進去，硬要推就得寫重播器，而重播器會讓時間軸變成假的。

本課程提供三份 Prometheus 設定檔：

```text
infra/prometheus/prometheus.macos.yml    macOS
infra/prometheus/prometheus.linux.yml    Linux
infra/prometheus/prometheus.windows.yml  Windows
```

三份都定義同一組 target：

```text
localhost:9090  prometheus        Prometheus 自己
localhost:9100  node-exporter     這台機器的真實網路指標（macOS / Linux）
localhost:9182  windows-exporter  這台機器的真實網路指標（Windows）
```

Prometheus 對 DOWN 的 target 會顯示為 `0`，不會阻止其他 target 正常收集。

三份設定檔都帶一行 `rule_files: ["alerts.yml"]`。這個相對路徑是相對設定檔自己的目錄解析的，所以指到的是 `infra/prometheus/alerts.yml`，不管你從哪個目錄啟動 Prometheus。那份檔案裡是打在 `node_exporter` 指標上的 recording rules 與 alert rules，工作坊 Lab 01 與 Lab 02 會拿它跟 pandas 那一邊對照。設定檔與規則檔可以先驗一次：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

看到 `SUCCESS: 1 rule files found` 與 `SUCCESS: 15 rules found` 就表示規則檔被正確找到。

先完成 [01a](01a-setup-macos-python-environment.md)、[01b](01b-setup-linux-python-environment.md) 或 [01c](01c-setup-windows-python-environment.md)，確認 conda 環境已建立。

## 啟動方式的陷阱：Prometheus 一定要載到本 repository 的設定檔

這一節請先讀完再往下做。用套件管理器的 service 方式啟動 Prometheus，例如 `brew services start prometheus` 或 `systemctl start prometheus`，載入的是該套件自己的預設設定檔（macOS 上是 `/opt/homebrew/etc/prometheus.yml`）。那份檔案只有 Prometheus 自己一個 target，沒有 `node-exporter`，也沒有 `alerts.yml` 的規則。

這個錯誤特別難自己發現，因為它不會報錯。Prometheus 是活的，node_exporter 是活的，Grafana 是活的，查 `up{job="prometheus"}` 回傳 `1`，每一項單獨看都正常，但沒有任何人去抓 `localhost:9100`，dashboard 第一列於是永遠空白。要看的是 job 存不存在，不是 job 的值是不是 `1`。

兩種啟動方式都可以，選一種做到底。

**方式一，直接指定 repository 內的設定檔。** 從 repository 根目錄執行，不需要複製任何檔案，改設定檔之後重啟就生效：

```bash
prometheus --config.file=infra/prometheus/prometheus.macos.yml --web.enable-lifecycle
```

Linux 換成 `prometheus.linux.yml`，Windows 換成 `prometheus.windows.yml`。

**方式二，把設定檔複製到套件的預設位置，再用 service 啟動。** 工作坊 notebook 用的是這一種，因為服務起來以後整個下午都不用管：

```bash
cp infra/prometheus/prometheus.macos.yml /opt/homebrew/etc/prometheus.yml
cp infra/prometheus/alerts.yml           /opt/homebrew/etc/alerts.yml
brew services restart prometheus
```

兩份都要複製。`rule_files` 是相對設定檔的目錄解析的，設定檔搬到 `/opt/homebrew/etc/` 之後，它找的就是 `/opt/homebrew/etc/alerts.yml`。之後每次改了 repository 裡的設定，都要重新複製一次。

方式二還要多做一件事。Homebrew 的 service 不是直接讀命令列參數，而是讀 `/opt/homebrew/etc/prometheus.args`，這份檔案預設沒有 `--web.enable-lifecycle`，於是 `curl -X POST http://localhost:9090/-/reload` 會回 `405 Method Not Allowed`。Lab 02 會用到那個 reload，所以先補上一行：

```bash
echo "--web.enable-lifecycle" >> /opt/homebrew/etc/prometheus.args
brew services restart prometheus
```

Intel Mac 的 Homebrew 前綴是 `/usr/local`，用 `brew --prefix` 確認自己那台是哪一個。

## macOS（Homebrew）

```bash
brew install prometheus
```

安裝後開一個新終端機，回到 repository 根目錄，用上一節任一種方式啟動。前景執行是最直接的：

```bash
prometheus --config.file=infra/prometheus/prometheus.macos.yml --web.enable-lifecycle
```

如果終端機顯示 `prometheus: command not found`，先確認 Homebrew 的 `bin` 目錄已加入 `PATH`：

```bash
brew --prefix
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## Linux（二進制）

```bash
PROM_VERSION="3.12.0"
curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
tar xvf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
cd "prometheus-${PROM_VERSION}.linux-amd64"
./prometheus --config.file=/path/to/aiops-anomaly-zero-to-hero/infra/prometheus/prometheus.linux.yml --web.enable-lifecycle
```

請先到 [prometheus.io/download](https://prometheus.io/download/) 確認目前最新版本，再更新 `PROM_VERSION`。也可以使用發行版套件管理器安裝，但版本可能落後官方 release。

若你的系統已透過套件管理器安裝 `prometheus` 指令，也可以在 repository 根目錄執行：

```bash
prometheus --config.file=infra/prometheus/prometheus.linux.yml --web.enable-lifecycle
```

用 `systemd` 服務啟動的話，跟 macOS 方式二一樣要把 `prometheus.linux.yml` 與 `alerts.yml` 一起複製到該服務讀的設定目錄（通常是 `/etc/prometheus/`），再 `sudo systemctl restart prometheus`。

其他發行版請參考[官方安裝文件](https://prometheus.io/docs/prometheus/latest/installation/)。

## Windows

1. 至 [prometheus.io/download](https://prometheus.io/download/) 下載 `prometheus-*windows-amd64.zip`。
2. 解壓縮到任意目錄，例如 `C:\prometheus`。
3. 開啟第二個 PowerShell，在 Prometheus 解壓縮目錄執行：

```powershell
.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle
```

瀏覽器開啟 [http://localhost:9090](http://localhost:9090) 確認是否正常運作。

## 確認安裝成功

瀏覽器開啟 [http://localhost:9090](http://localhost:9090)，在 Expression 欄位輸入 `up`，點擊 **Execute**。

先看 job 清單，再看值：

```promql
up{job="prometheus"}
```

```promql
up{job="node-exporter"}
```

Windows 改查：

```promql
up{job="windows-exporter"}
```

`job="prometheus"` 應該是 `1`。`job="node-exporter"` 在你完成 [04-install-node-exporter.md](04-install-node-exporter.md) 之前會是 `0`，那是正常的；重點是這一筆要存在。查詢結果裡完全沒有這個 job，表示 Prometheus 載入了套件預設設定檔，回頭看〈啟動方式的陷阱〉。

規則檔有沒有載進來，查一條 recording rule 就知道：

```promql
net:traffic_bps
```

node_exporter 起來幾分鐘後這條應該有值。查不到而 `up{job="node-exporter"}` 是 `1`，表示設定檔載到了但 `alerts.yml` 沒跟著搬過去。

Prometheus 的 target 頁面（`http://localhost:9090/targets`）是同一件事的圖形版，卡住的時候看那一頁最快。

## 常見問題

**Grafana dashboard 第一列一直是空的？**
在 Prometheus 查 `up`，看回傳結果裡有沒有 `job="node-exporter"` 這一筆。找不到就是 Prometheus 載入了套件預設設定檔而不是本 repository 的設定檔，細節見〈啟動方式的陷阱〉。有這一筆但值是 `0`，代表設定對了，exporter 還沒起來，去做 [04-install-node-exporter.md](04-install-node-exporter.md)。

**Grafana dashboard 第二列與第三列一直是空的？**
那兩列讀的是 `outputs/workshop/` 裡的檔案，跟 Prometheus 無關。確認 `python -m http.server 8080 --directory outputs/workshop` 這個終端機還開著，並且對應的 lab 已經跑完寫出 CSV。

**`curl -X POST http://localhost:9090/-/reload` 回 405？**
Prometheus 啟動時沒有帶 `--web.enable-lifecycle`。前景啟動就直接加這個參數；`brew services` 啟動就把它加進 `/opt/homebrew/etc/prometheus.args` 再重啟服務。

**瀏覽器無法開啟 `localhost:9090`？**
確認 Prometheus 指令視窗仍在執行中。若看到 `address already in use`，表示 9090 連接埠已被占用，請先關閉舊的 Prometheus 程序。

**macOS 顯示 `brew: command not found`？**
請先安裝 Homebrew：[https://brew.sh](https://brew.sh)，或改用 Prometheus 官方下載頁的 binary 安裝方式。

## 下一步

繼續 [03a-install-grafana-local.md](03a-install-grafana-local.md) 安裝 Grafana Local，並裝好工作坊 dashboard 需要的 Infinity datasource。

工作坊也需要 node_exporter，可以同步完成 [04-install-node-exporter.md](04-install-node-exporter.md)。`alerts.yml` 的規則全部打在 node_exporter 指標上，沒有它，recording rule 與 alert rule 都不會有值。

完成 Grafana Local 後，若想額外把指標推送到雲端，可選擇繼續 [03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)（選用）。
