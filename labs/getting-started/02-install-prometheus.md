# 安裝並啟動 Prometheus

官方文件：[安裝說明](https://prometheus.io/docs/prometheus/latest/installation/)、[下載頁](https://prometheus.io/download/)

Prometheus 是系統級監控服務，安裝方式依作業系統與權限設定而異。conda 環境只處理 notebook 需要的套件，Prometheus 要自己安裝。開始之前先完成 [01-setup-python-environment.md](01-setup-python-environment.md)。

## 這門課的 Prometheus 抓什麼

只有兩個 scrape target：Prometheus 自己，以及 `node_exporter`（Windows 上是 `windows_exporter`）。兩者都是官方 binary。

| target | job | 內容 |
| --- | --- | --- |
| `localhost:9090` | `prometheus` | Prometheus 自己 |
| `localhost:9100` | `node-exporter` | 這台機器的真實網路指標（macOS / Linux） |
| `localhost:9182` | `windows-exporter` | 這台機器的真實網路指標（Windows） |

Notebook 算出來的結果不經過 Prometheus。它用 `to_csv()` 與 `savefig()` 寫進 `outputs/workshop/`，一行 `python -m http.server` 把資料夾開啟給外部讀取，Grafana 端用 Infinity datasource 讀檔案。分開的理由是儲存模型：Prometheus 是 pull 模型，時間戳來自 scrape 的當下，一個月的歷史分數推不進去，硬要推就得寫重播器，而重播器會讓時間軸變成假的。

設定檔按平台分成三份，`infra/prometheus/prometheus.{macos,linux,windows}.yml`，target 三份都一樣。Prometheus 對 DOWN 的 target 顯示 `0`，不會影響其他 target 收集。

三份都帶一行 `rule_files: ["alerts.yml"]`。這個相對路徑是相對設定檔自己的目錄解析的，所以指到的永遠是 `infra/prometheus/alerts.yml`，跟你從哪個目錄啟動無關。那份檔案裡是打在 `node_exporter` 指標上的 recording rules 與 alert rules，工作坊 Lab 01 與 Lab 02 會拿它跟 pandas 那一邊對照。先驗一次：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

看到 `SUCCESS: 1 rule files found` 與 `SUCCESS: 15 rules found` 就表示 Prometheus 找到了規則檔。

## 啟動方式的陷阱：一定要載到本 repository 的設定檔

用套件管理器的 service 方式啟動，例如 `brew services start prometheus` 或 `systemctl start prometheus`，載入的是該套件自己的預設設定檔（macOS 上是 `/opt/homebrew/etc/prometheus.yml`）。那份檔案只有 Prometheus 自己一個 target，沒有 `node-exporter`，也沒有 `alerts.yml` 的規則。

這個錯誤難自己發現，因為它不會出錯。Prometheus 是活的，node_exporter 是活的，Grafana 是活的，查詢 `up{job="prometheus"}` 回傳 `1`，每一項單獨看都正常，但沒有任何人去抓 `localhost:9100`，dashboard 第一列於是永遠空白。要看的是 job 存不存在，不是 job 的值是不是 `1`。

兩種啟動方式都可以，選一種做到底。

**方式一，直接指定 repository 內的設定檔。** 從 repository 根目錄執行，不需要複製任何檔案，改完設定重啟就生效：

```bash
prometheus --config.file=infra/prometheus/prometheus.macos.yml --web.enable-lifecycle
```

Linux 換成 `prometheus.linux.yml`，Windows 是 `.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle`。

**方式二，把設定檔複製到套件的預設位置，再用 service 啟動。** 工作坊 notebook 用的是這一種，因為服務起來以後整個下午都不用管：

```bash
cp infra/prometheus/prometheus.macos.yml /opt/homebrew/etc/prometheus.yml
cp infra/prometheus/alerts.yml           /opt/homebrew/etc/alerts.yml
brew services restart prometheus
```

兩份都要複製。`rule_files` 是相對設定檔的目錄解析的，設定檔搬到 `/opt/homebrew/etc/` 之後，它找的就是 `/opt/homebrew/etc/alerts.yml`。之後每次改了 repository 裡的設定，都要重新複製一次。Linux 的 systemd 服務同理，目標目錄通常是 `/etc/prometheus/`。

方式二還要多做一件事。Homebrew 的 service 讀的是 `/opt/homebrew/etc/prometheus.args` 而不是命令列參數，這份檔案預設沒有 `--web.enable-lifecycle`，於是 `curl -X POST http://localhost:9090/-/reload` 會回 `405 Method Not Allowed`。Lab 02 會用到那個 reload：

```bash
echo "--web.enable-lifecycle" >> /opt/homebrew/etc/prometheus.args
brew services restart prometheus
```

Intel Mac 的 Homebrew 前綴是 `/usr/local`，用 `brew --prefix` 確認自己那台是哪一個。

## 取得 Prometheus

**macOS：** `brew install prometheus`。顯示 `command not found` 時，用 `brew --prefix` 確認 Homebrew 的 `bin` 已加入 `PATH`。

**Linux：** 到[下載頁](https://prometheus.io/download/)確認最新版本，再更新 `PROM_VERSION`。

```bash
PROM_VERSION="3.12.0"
curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
tar xvf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
cd "prometheus-${PROM_VERSION}.linux-amd64"
```

發行版套件管理器也可以，但版本可能落後官方 release。

**Windows：** 到[下載頁](https://prometheus.io/download/)下載 `prometheus-*windows-amd64.zip`，解壓縮到任意目錄，例如 `C:\prometheus`，開啟第二個 PowerShell 在該目錄啟動。

取得之後回到上一節選一種方式啟動，然後開啟 <http://localhost:9090>。

## 確認安裝成功

在 <http://localhost:9090> 的 Expression 欄位查詢 `up`。先看 job 清單，再看值：

```promql
up{job="prometheus"}
```

`job="prometheus"` 應該是 `1`。`job="node-exporter"`（Windows 是 `windows-exporter`）在你完成 [04-install-node-exporter.md](04-install-node-exporter.md) 之前會是 `0`，那是正常的，重點是這一筆要存在。查詢結果裡完全沒有這個 job，表示 Prometheus 載入了套件預設設定檔，回頭看〈啟動方式的陷阱〉。

規則檔有沒有載進來，查詢一條 recording rule 就知道：

```promql
net:traffic_bps
```

node_exporter 啟動幾分鐘後這條應該有值。查詢不到而 `up{job="node-exporter"}` 是 `1`，表示設定檔載到了但 `alerts.yml` 沒跟著搬過去。

<http://localhost:9090/targets> 是同一件事的圖形版，卡住的時候看那一頁最快。

## 常見問題

**Grafana dashboard 第一列一直是空的？**
查詢 `up`，看回傳結果裡有沒有 `job="node-exporter"` 這一筆。找不到就是載入了套件預設設定檔，見〈啟動方式的陷阱〉。有這一筆但值是 `0`，代表設定對了、exporter 還沒啟動，去做 [04-install-node-exporter.md](04-install-node-exporter.md)。

**Grafana dashboard 第二列與第三列一直是空的？**
那兩列讀的是 `outputs/workshop/` 裡的檔案，跟 Prometheus 無關。確認 `python -m http.server 8080 --directory outputs/workshop` 這個終端機還開著，並且對應的 lab 已經執行完寫出 CSV。

**`curl -X POST http://localhost:9090/-/reload` 回 405？**
啟動時沒有帶 `--web.enable-lifecycle`。前景啟動就直接加這個參數，`brew services` 啟動就把它加進 `/opt/homebrew/etc/prometheus.args` 再重啟服務。

**瀏覽器無法開啟 `localhost:9090`？**
確認 Prometheus 指令視窗仍在執行中。看到 `address already in use` 表示 9090 連接埠已被占用，先關閉舊的 Prometheus 程序。

**macOS 顯示 `brew: command not found`？**
先安裝 [Homebrew](https://brew.sh)，或改用官方下載頁的 binary。

## 下一步

[03a-install-grafana-local.md](03a-install-grafana-local.md) 安裝 Grafana Local 與 Infinity datasource，[04-install-node-exporter.md](04-install-node-exporter.md) 安裝 node_exporter。`alerts.yml` 的規則全部打在 node_exporter 指標上，沒有它，recording rule 與 alert rule 都不會有值。

想把指標推送到雲端是選用延伸，見 [03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)。
