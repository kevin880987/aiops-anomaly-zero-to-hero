# 初次使用設定指南

這份文件給第一次執行 `aiops-anomaly-zero-to-hero` 的學員使用。Python 套件使用 conda 環境管理；Prometheus 與 Grafana 是本機監控工具，依作業系統使用原生安裝方式。

---

## 路線圖

課程環境分兩條準備線，可以並行進行，但 Step 3 需要兩條都完成後才能執行。

```text
Step 1   Python / conda 環境建立（擇一）
            macOS   → 01a-setup-macos-python-environment.md
            Linux   → 01b-setup-linux-python-environment.md
            Windows → 01c-setup-windows-python-environment.md

Step 2   監控工具安裝與啟動
            Step 2a  啟動課程 exporter，安裝並啟動 Prometheus → 02-install-prometheus.md
            Step 2b  安裝 node_exporter（實戰工作坊必須）→ 04-install-node-exporter.md
            Step 2c  安裝 Grafana，連接 Prometheus，匯入 dashboard → 03-install-grafana.md

Step 3   開啟 Labs，開始課程

         實戰工作坊版（workshop）
            labs/workshop/00_observability_stack_and_promql.ipynb
            labs/workshop/01_network_traffic_feature_engineering.ipynb
            labs/workshop/02_anomaly_detection_and_alerting.ipynb
            labs/workshop/08_agentic_ai_rca_capstone.ipynb

         完整自學版（9 labs）
            labs/self-study/00_observability_stack.ipynb
            labs/self-study/01_time_series_features.ipynb
            … labs/self-study/08_deploy_to_production.ipynb
```

---

## Step 1 — Python / conda 環境建立

根據電腦作業系統，開啟對應文件：

| 作業系統 | 文件 |
| --- | --- |
| macOS 12 以上 | [01a-setup-macos-python-environment.md](01a-setup-macos-python-environment.md) |
| Linux（Ubuntu / Debian 等） | [01b-setup-linux-python-environment.md](01b-setup-linux-python-environment.md) |
| Windows 10 / 11 | [01c-setup-windows-python-environment.md](01c-setup-windows-python-environment.md) |

三種平台都使用同一份 `environment.yml` 建立名為 `aiops-anomaly-zero-to-hero` 的 conda 環境。macOS 與 Windows 的 bootstrap 腳本會自動檢查現有環境，若已符合課程需求則跳過更新，並執行 `labs/getting-started/scripts/validate_setup.py` 確認 repository 檔案、notebook JSON、dashboard JSON 與 Python 套件都可用。Linux 使用者請依 Linux 文件手動執行同一個驗證腳本：

```bash
conda activate aiops-anomaly-zero-to-hero
python labs/getting-started/scripts/validate_setup.py --repo-only
```

如果你只想先建立環境、不立刻開啟 JupyterLab：

```bash
# macOS
bash labs/getting-started/scripts/bootstrap_macos.sh --no-launch
```

```bash
# Linux
conda env create -f environment.yml
conda activate aiops-anomaly-zero-to-hero
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1 -NoLaunch
```

---

## Step 2a — 啟動課程 exporter，安裝並啟動 Prometheus

[02-install-prometheus.md](02-install-prometheus.md)

Prometheus 是本機監控服務，不安裝在 conda 環境裡。課程的 `infra/exporter.py` 則使用 conda 環境中的 `prometheus_client`，把合成資料轉成 Prometheus 可抓取的 metrics。macOS / Linux 使用 `infra/prometheus/prometheus.yml`。Windows 使用 `infra/prometheus/prometheus.windows.yml`，因為 Windows 的 exporter 預設 port 與 metrics 名稱不同。

---

## Step 2b — 安裝 node_exporter（實戰工作坊必須）

[04-install-node-exporter.md](04-install-node-exporter.md)

node_exporter 把你的 PC 變成被監控目標，提供 CPU、網路、磁碟等 OS metrics 給 Prometheus 抓取。工作坊短版會查詢這些即時 OS 指標。完整自學版若只使用合成 CSV 資料，可以先跳過此步驟。

---

## Step 2c — 安裝 Grafana 並連接 Prometheus

[03-install-grafana.md](03-install-grafana.md)

涵蓋各平台安裝、首次登入、將 Prometheus 設為 Grafana 資料來源，以及匯入課程 dashboard。Grafana 不是 Python 套件，因此不由 conda 腳本安裝。

---

## Step 3 — 開始課程

Step 1 與 Step 2 都完成後，在 JupyterLab 中選擇一條路徑：

- 工作坊短版：從 `labs/workshop/00_observability_stack_and_promql.ipynb` 開始。
- 完整自學版：從 `labs/self-study/00_observability_stack.ipynb` 開始。

---

## 文件索引

| 編號 | 文件 | 用途 |
| --- | --- | --- |
| 01a | [01a-setup-macos-python-environment.md](01a-setup-macos-python-environment.md) | macOS conda 環境建立與 JupyterLab 啟動 |
| 01b | [01b-setup-linux-python-environment.md](01b-setup-linux-python-environment.md) | Linux conda 環境建立與 JupyterLab 啟動 |
| 01c | [01c-setup-windows-python-environment.md](01c-setup-windows-python-environment.md) | Windows conda 環境建立與 JupyterLab 啟動 |
| 02 | [02-install-prometheus.md](02-install-prometheus.md) | Prometheus 各平台安裝 |
| 03 | [03-install-grafana.md](03-install-grafana.md) | Grafana 各平台安裝與 Prometheus 資料來源連接 |
| 04 | [04-install-node-exporter.md](04-install-node-exporter.md) | node_exporter 安裝（實戰工作坊必須） |
