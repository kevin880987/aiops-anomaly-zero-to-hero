# 安裝並啟動 Prometheus

官方文件：[安裝說明](https://prometheus.io/docs/prometheus/latest/installation/)、[下載頁](https://prometheus.io/download/)

Prometheus 每五秒去抓一次 exporter 的 `/metrics`，把時間序列存起來給 Grafana 查詢。開始之前先完成 [01-setup-python-environment.md](01-setup-python-environment.md)。

## 1. 安裝

**macOS：**

```bash
brew install prometheus
```

**Linux：** 到[下載頁](https://prometheus.io/download/)確認最新版本再填入 `PROM_VERSION`。

```bash
PROM_VERSION="3.12.0"
curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
tar xvf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
cd "prometheus-${PROM_VERSION}.linux-amd64"
```

**Windows：** 在[下載頁](https://prometheus.io/download/)下載 `prometheus-*windows-amd64.zip`，解壓縮到任意目錄，例如 `C:\prometheus`。

## 2. 啟動

從 repository 根目錄執行，設定檔換成自己那一份：

```bash
prometheus --config.file=infra/prometheus/prometheus.macos.yml --web.enable-lifecycle
```

Windows 是 `.\prometheus.exe --config.file="C:\path\to\aiops-anomaly-zero-to-hero\infra\prometheus\prometheus.windows.yml" --web.enable-lifecycle`。

這個視窗留著。**不要用 `brew services start prometheus` 或 `systemctl start prometheus` 直接啟動**，那會載入套件自己的預設設定檔，理由與正確做法見下面〈用 service 啟動〉。

## 3. 驗收

開啟 <http://localhost:9090>，在 Expression 欄位查詢 `up`。

先看 job 清單再看值。`job="prometheus"` 應該是 `1`；`job="node-exporter"`（Windows 是 `windows-exporter`）在你完成 [04-install-node-exporter.md](04-install-node-exporter.md) 之前會是 `0`，那是正常的，重點是這一筆要存在。

查詢結果裡完全沒有 `node-exporter` 這一筆，就是設定檔載錯了，往下看〈用 service 啟動〉。

<http://localhost:9090/targets> 是同一件事的圖形介面，排查時從那一頁看最快。

## 用 service 啟動

`brew services start prometheus` 與 `systemctl start prometheus` 載入的是套件自己的預設設定檔（macOS 上是 `/opt/homebrew/etc/prometheus.yml`）。那份檔案只有 Prometheus 自己一個 target，沒有 `node-exporter`，也沒有 `alerts.yml` 的規則。

這個錯誤難自己發現，因為它不會出錯。Prometheus 是活的，node_exporter 是活的，Grafana 是活的，查詢 `up{job="prometheus"}` 回傳 `1`，每一項單獨看都正常，但沒有任何人去抓 `localhost:9100`，dashboard 第一列於是永遠空白。要看的是 job 存不存在，不是 job 的值是不是 `1`。

要用 service 方式（啟動之後無須介入），先把檔案複製到套件的預設位置：

```bash
cp infra/prometheus/prometheus.macos.yml /opt/homebrew/etc/prometheus.yml
cp infra/prometheus/alerts.yml           /opt/homebrew/etc/alerts.yml
echo "--web.enable-lifecycle" >> /opt/homebrew/etc/prometheus.args
brew services restart prometheus
```

兩份設定檔都要複製，`rule_files` 是相對設定檔的目錄解析的。第三行是因為 Homebrew 的 service 讀 `prometheus.args` 而不是命令列參數，少了它，Lab 02 用到的 `curl -X POST http://localhost:9090/-/reload` 會回 `405`。之後每次改了 repository 裡的設定，都要重新複製一次。

Intel Mac 的前綴是 `/usr/local`，用 `brew --prefix` 確認。Linux 的 systemd 同理，目標目錄通常是 `/etc/prometheus/`。

## 這門課抓什麼

只有兩個 scrape target，兩個都是官方 binary：

| target | job | 內容 |
| --- | --- | --- |
| `localhost:9090` | `prometheus` | Prometheus 自己 |
| `localhost:9100` | `node-exporter` | 這台機器的真實網路指標（macOS / Linux） |
| `localhost:9182` | `windows-exporter` | 這台機器的真實網路指標（Windows） |

Notebook 算出來的結果不經過 Prometheus，而是用 `to_csv()` 與 `savefig()` 寫進 `outputs/workshop/`，由 Grafana 的 Infinity datasource 讀檔案。

技術上灌得進去，只是課堂上的成本不划算。`promtool tsdb create-blocks-from openmetrics` 可以把帶時間戳的歷史樣本壓成 TSDB block，時間戳完整保留；代價是一整個月的分數會產生數百個 block，而且要把 block 搬進 Prometheus 的 data 目錄再重啟，每調一次參數重新執行 notebook 就得再走一次。

真實部署走的是上面那條路：分數由服務算完曝露在 `/metrics`，Prometheus scrape，Grafana 查詢。所以課程的 dashboard 把 Infinity 面板的欄位命名成 `aiops_*` 的 metric 名，port 用 dashboard 變數篩選，對應的就是 PromQL 的 label selector。上線時把 datasource 換成 Prometheus，面板不用重做。

三份設定檔都帶一行 `rule_files: ["alerts.yml"]`，指到的永遠是 `infra/prometheus/alerts.yml`，跟你從哪個目錄啟動無關。那份檔案裡是打在 `node_exporter` 指標上的 recording rules 與 alert rules，工作坊 Lab 01 與 Lab 02 會拿它跟 pandas 那一邊對照。要先驗設定檔與規則檔：

```bash
promtool check config infra/prometheus/prometheus.macos.yml
```

看到 `SUCCESS: 1 rule files found` 與 `SUCCESS: 15 rules found` 就表示 Prometheus 找到了規則檔。規則有沒有生效，等 node_exporter 啟動之後查詢 `net:traffic_bps`，有值就是通了。

## 常見問題

**Grafana dashboard 第一列一直是空的？**
查詢 `up`，看有沒有 `job="node-exporter"` 這一筆。找不到就是載入了套件預設設定檔，見〈用 service 啟動〉。有這一筆但值是 `0`，代表設定對了、exporter 還沒啟動，去做 [04-install-node-exporter.md](04-install-node-exporter.md)。

**Grafana dashboard 第二列與第三列一直是空的？**
那兩列讀的是 `outputs/workshop/` 裡的檔案，跟 Prometheus 無關。確認 `python -m http.server 8080 --directory outputs/workshop` 這個終端機仍在執行，並且對應的 lab 已經執行完並寫出 CSV。

**`curl -X POST http://localhost:9090/-/reload` 回 405？**
啟動時沒有帶 `--web.enable-lifecycle`。前景啟動就直接加這個參數，service 啟動就把它加進 `prometheus.args` 再重啟。

**瀏覽器無法開啟 `localhost:9090`？**
確認指令視窗仍在執行中。看到 `address already in use` 表示 9090 已被占用，先關閉舊的 Prometheus 程序。

**macOS 顯示 `brew: command not found`？**
先安裝 [Homebrew](https://brew.sh)，或改用官方下載頁的 binary。

## 下一步

[04-install-node-exporter.md](04-install-node-exporter.md) 與 [03a-install-grafana-local.md](03a-install-grafana-local.md)。`alerts.yml` 的規則全部打在 node_exporter 指標上，沒有它，recording rule 與 alert rule 都不會有值。
