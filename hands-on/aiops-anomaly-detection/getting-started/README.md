# 初次使用設定指南

這份文件給第一次執行 `aiops-anomaly-detection` 的學員使用。涵蓋範圍：Python 環境建立、JupyterLab 啟動，以及 Prometheus / Grafana 的安裝與串接。

---

## 路線圖

課程環境分兩條準備線，可以並行進行，但 Step 3 需要兩條都完成後才能執行。

```text
Step 1   Python 環境建立（擇一）
            macOS   → 01a-setup-macos-python-environment.md
            Windows → 01b-setup-windows-python-environment.md

Step 2   監控工具安裝
            Step 2a  安裝 Prometheus → 02-install-prometheus.md
            Step 2b  安裝 Grafana 並連接 Prometheus → 03-install-grafana.md

Step 3   開啟 Notebooks，開始課程
            Notebook1_Time_Series_Features.ipynb
            Notebook2_Baseline_Anomaly_Detection.ipynb
```

---

## Step 1 — Python 環境建立

根據電腦作業系統，開啟對應文件並完成三個步驟（進入專案目錄 → 建立環境 → 啟動 JupyterLab）：

| 作業系統 | 文件 |
|---|---|
| macOS 12 以上 | [01a-setup-macos-python-environment.md](01a-setup-macos-python-environment.md) |
| Windows 10 / 11 | [01b-setup-windows-python-environment.md](01b-setup-windows-python-environment.md) |

---

## Step 2a — 安裝 Prometheus

[02-install-prometheus.md](02-install-prometheus.md)

涵蓋 macOS（Homebrew）、Windows（zip 下載）、Linux（apt）三種安裝方式，以及確認安裝成功的方法。

---

## Step 2b — 安裝 Grafana 並連接 Prometheus

[03-install-grafana.md](03-install-grafana.md)

涵蓋各平台安裝、首次登入，以及將 Prometheus 設為 Grafana 資料來源的步驟。

---

## Step 3 — 開始課程

Step 1 與 Step 2 都完成後，在 JupyterLab 中依序執行：

1. `Notebook1_Time_Series_Features.ipynb`
2. `Notebook2_Baseline_Anomaly_Detection.ipynb`

---

## 文件索引

| 編號 | 文件 | 用途 |
| --- | --- | --- |
| 01a | [01a-setup-macos-python-environment.md](01a-setup-macos-python-environment.md) | macOS Python 環境建立與 JupyterLab 啟動 |
| 01b | [01b-setup-windows-python-environment.md](01b-setup-windows-python-environment.md) | Windows Python 環境建立與 JupyterLab 啟動 |
| 02 | [02-install-prometheus.md](02-install-prometheus.md) | Prometheus 各平台安裝 |
| 03 | [03-install-grafana.md](03-install-grafana.md) | Grafana 各平台安裝與 Prometheus 資料來源連接 |
