# 環境就緒確認

這份文件是最終把關。不論你用哪種方式完成環境設定，只要以下所有檢查通過，就可以開始課程。

---

## 你需要什麼

不同學習路徑對環境的要求不同：

| 元件 | 完整自學版（self-study） | 實戰工作坊（workshop） |
| --- | --- | --- |
| Python 3.12 + 必要套件 | 必須 | 必須 |
| 可執行 Notebook 的工具 | 必須 | 必須 |
| Prometheus | 必須（Lab 00 開始） | 必須 |
| Grafana Local | 必須 | 必須 |
| Grafana Cloud | 選用 | 選用 |
| node_exporter / windows_exporter | 選用 | **必須** |

---

## 檢查 1 — 自動驗證腳本

這個腳本一次檢查所有 Python 套件、Python 版本、repository 必要檔案，以及各項服務是否可以連線。

在啟用了 `aiops-anomaly-zero-to-hero` conda 環境（或你自己的 Python 環境）後，從 repository 根目錄執行：

```bash
python labs/getting-started/scripts/validate_setup.py
```

輸出範例（全部通過）：

```text
Repository root: /path/to/aiops-anomaly-zero-to-hero
Platform: Darwin 24.x.x (arm64)

Required repository files
  [OK] ok file: README.md
  [OK] ok file: environment.yml
  ...

Notebook and dashboard JSON
  [OK] ok JSON: labs/workshop/00_observability_stack_and_promql.ipynb
  ...

Python environment
  [OK] ok Python: 3.12.x
  [OK] ok package: numpy 1.26.x
  [OK] ok package: pandas 2.x.x
  [OK] ok package: scikit-learn 1.x.x
  [OK] ok package: matplotlib 3.x.x
  [OK] ok package: jupyterlab 4.x.x
  [OK] ok package: prometheus-client 0.x.x

Optional local services
  [OK] reachable service: course exporter (http://localhost:8000/metrics)
  [OK] reachable service: Prometheus (http://localhost:9090/-/ready)
  [OK] reachable service: Grafana Local (http://localhost:3000/api/health)
  [..] not running yet: node_exporter (http://localhost:9100/metrics)

Required checks passed.
```

`[OK]` 表示通過；`[!!]` 表示必須修正；`[..]` 表示服務未執行（選用項目不影響整體結果）。

**只想驗證 repository 結構、暫時跳過 Python 和服務檢查：**

```bash
python labs/getting-started/scripts/validate_setup.py --repo-only
```

---

## 檢查 2 — Notebook 工具

你可以用任何能執行 Jupyter Notebook 的工具，不限定 JupyterLab。

### 選項 A：JupyterLab

在課程環境中啟動：

```bash
# conda 環境已啟用
jupyter lab
```

瀏覽器會自動開啟 `http://localhost:8888`。你應該看到類似下圖的介面：

![JupyterLab Interface](https://jupyterlab.readthedocs.io/en/stable/_images/interface-jupyterlab.png)

*圖片來源：[JupyterLab 官方文件](https://jupyterlab.readthedocs.io/en/stable/getting_started/overview.html)*

確認事項：

- 左側 file browser 可以看到 `labs/` 目錄
- 點開任一 `.ipynb` 文件，右上角顯示 **Python 3（ipykernel）** kernel
- 在 cell 執行 `import pandas; print(pandas.__version__)` 有輸出即可

### 選項 B：VS Code（Jupyter 擴充套件）

如果你已安裝 VS Code 的 Jupyter 擴充套件，直接在 VS Code 中開啟 `.ipynb` 文件也完全可以。官方文件：[VS Code Jupyter 擴充套件](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter)

開啟 notebook 後，在右上角選擇 kernel → 選 `aiops-anomaly-zero-to-hero`（若使用 conda 環境）。

### 選項 C：Classic Notebook / JupyterHub

Classic Notebook（`jupyter notebook`）或 JupyterHub 也支援。確認 kernel 使用的 Python 環境包含課程必要套件即可。

### Kernel 確認

不論哪種工具，在 notebook 中執行以下 cell 確認環境：

```python
import sys, numpy, pandas, sklearn, matplotlib, jupyterlab
print("Python:", sys.version)
print("NumPy:", numpy.__version__)
print("Pandas:", pandas.__version__)
print("scikit-learn:", sklearn.__version__)
```

輸出中 Python 版本應為 3.12 以上，套件版本符合 `environment.yml` 中的下限即可。

---

## 檢查 3 — Prometheus

官方文件：[prometheus.io/docs/prometheus/latest/getting\_started](https://prometheus.io/docs/prometheus/latest/getting_started/)

Prometheus 需要在 `http://localhost:9090` 可以連線。

### 確認 Prometheus 正在執行

在瀏覽器開啟 [http://localhost:9090](http://localhost:9090)。你應該看到 Prometheus 的 Expression Browser：

![Prometheus Expression Browser](https://prometheus.io/assets/docs/instrumenting_architecture.png)

點擊上方選單的 **Status → Targets**（或直接開啟 [http://localhost:9090/targets](http://localhost:9090/targets)）。

成功狀態如下：

- `csv-exporter` 目標狀態為 **UP**（綠色）
- 如果已安裝 node_exporter，`node-exporter` 目標也應顯示 **UP**

![Prometheus Targets Page — all UP](https://prometheus.io/assets/docs/grafana_prometheus.png)

*[Prometheus 官方 Targets 頁面說明](https://prometheus.io/docs/prometheus/latest/getting_started/#configuring-prometheus-to-monitor-itself)*

如果目標顯示 **DOWN**，代表對應服務未執行。先確認 `infra/exporter.py` 正在執行，再重新確認。

### 快速 PromQL 驗證

在 Expression Browser（[http://localhost:9090/graph](http://localhost:9090/graph)）輸入以下查詢，點擊 **Execute**：

```promql
up
```

回傳結果中，`job="csv-exporter"` 的值應為 `1`。

---

## 檢查 4 — Grafana Local

設定步驟：[03a-install-grafana-local.md](03a-install-grafana-local.md)

瀏覽器開啟 [http://localhost:3000](http://localhost:3000)，登入後進入 **Explore**，輸入：

```promql
up{job="csv-exporter"}
```

值為 `1` 即表示 Grafana Local 與 Prometheus 連線正常。

### 確認課程 Dashboard 可以載入

左側選單 → **Dashboards**，找到已匯入的 `network_metrics` dashboard。點開後若資料尚未進來 panel 會顯示 `No data`，但不報錯即為正常。

---

## 延伸選項 — Grafana Cloud（選用）

完成 Grafana Local 後，可選擇另外設定 Grafana Cloud，將本機 Prometheus 指標同步推送到雲端。設定步驟：[03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)。

開啟你的 Grafana Cloud 網址（`https://yourname.grafana.net`），進入 **Explore**，資料來源選 **Prometheus**，查詢 `up{job="csv-exporter"}` 值為 `1` 即表示 remote_write 正在推送指標。

---

## 檢查 5 — node_exporter / windows_exporter（workshop 必須）

官方文件：[prometheus.io/docs/guides/node-exporter](https://prometheus.io/docs/guides/node-exporter/)

工作坊版 Lab 00 需要即時 OS 指標。確認 exporter 正在執行：

### macOS / Linux（node\_exporter）

```bash
curl -s http://localhost:9100/metrics | grep node_network_receive_bytes_total | head -3
```

有輸出（包含 `node_network_receive_bytes_total` 開頭的指標）即表示正常。接著在 Prometheus 執行：

```promql
node_network_receive_bytes_total{device!~"lo|docker.*|veth.*"}
```

應該看到你的網路介面（macOS 通常是 `en0`，Linux 通常是 `eth0` 或 `ens3`）。

### Windows（windows\_exporter）

在瀏覽器開啟 [http://localhost:9182/metrics](http://localhost:9182/metrics)，頁面應顯示大量指標文字。接著在 Prometheus 執行：

```promql
windows_net_bytes_received_total
```

有結果即可。

---

## 最終確認表

跑完以上步驟後，自己勾選一遍：

### 完整自學版（self-study）

- [ ] `validate_setup.py` 無 `[!!]` 錯誤
- [ ] 可以在 notebook 工具中開啟 `labs/self-study/00_observability_stack.ipynb` 並執行 cell
- [ ] Prometheus 在 `http://localhost:9090` 可以連線
- [ ] `up{job="csv-exporter"}` 值為 `1`
- [ ] Grafana Local `up{job="csv-exporter"}` 值為 `1`（`http://localhost:3000`）

**以上通過，可以從 `labs/self-study/00_observability_stack.ipynb` 開始。**

### 實戰工作坊（workshop）

- [ ] 以上自學版所有項目通過
- [ ] `http://localhost:9100/metrics`（或 Windows 的 `:9182`）有回應
- [ ] Prometheus Targets 頁面 `node-exporter` 目標為 UP

**以上通過，可以從 `labs/workshop/00_observability_stack_and_promql.ipynb` 開始。**

---

## 常見問題

### `validate_setup.py` 出現 `[!!] missing Python package`

確認你在正確的 Python 環境中執行（conda 用 `conda activate aiops-anomaly-zero-to-hero`，VS Code 用右下角 Python interpreter 切換至課程環境）。

### Prometheus `csv-exporter` 顯示 DOWN

先確認 `python infra/exporter.py` 正在另一個終端機執行。Prometheus 每 15 秒抓一次，啟動後等待最多 30 秒。

### 無法連線 `http://localhost:9090`

確認 Prometheus 程序正在執行。macOS 用 `brew services list | grep prometheus`；Linux 用 `systemctl status prometheus`；Windows 查「服務」管理員。

### JupyterLab 找不到 kernel

執行 `python -m ipykernel install --user --name aiops-anomaly-zero-to-hero` 再重新整理 JupyterLab。

### Grafana Local 無法連線 `http://localhost:3000`

確認 Grafana 服務已啟動。macOS 用 `brew services list | grep grafana`；Linux 用 `systemctl status grafana-server`；Windows 開「服務」管理員找 `Grafana`。

### Grafana Cloud Explore 查不到指標

確認 prometheus.yml 的 remote_write url、username、password 已填入正確值，且 Prometheus 在修改後重啟。等待 30 秒後再試。詳細步驟見 [03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)。

---

## 參考資源

| 工具 | 官方文件 |
| --- | --- |
| Prometheus | [prometheus.io/docs/prometheus/latest/getting\_started](https://prometheus.io/docs/prometheus/latest/getting_started/) |
| Prometheus PromQL | [prometheus.io/docs/prometheus/latest/querying/basics](https://prometheus.io/docs/prometheus/latest/querying/basics/) |
| Grafana Cloud | [grafana.com/docs/grafana-cloud/send-data/metrics/metrics-prometheus](https://grafana.com/docs/grafana-cloud/send-data/metrics/metrics-prometheus/) |
| JupyterLab | [jupyterlab.readthedocs.io/en/stable/getting\_started/overview.html](https://jupyterlab.readthedocs.io/en/stable/getting_started/overview.html) |
| node\_exporter | [prometheus.io/docs/guides/node-exporter](https://prometheus.io/docs/guides/node-exporter/) |
| windows\_exporter | [github.com/prometheus-community/windows\_exporter](https://github.com/prometheus-community/windows_exporter) |
