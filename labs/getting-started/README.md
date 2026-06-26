# Getting started

這一頁是課程 setup 的主入口。學員只需要照順序做；安裝細節已拆到各平台或工具自己的文件。

本課程支援 macOS、Linux、Windows。請只執行自己作業系統的指令，不要混用不同 OS 的安裝方式。

---

## 0. 先選你的起點

### A. 已經有 Python / conda 環境

直接開啟檢查 notebook：

```text
labs/getting-started/00-check-your-setup.ipynb
```

它會檢查目前 notebook kernel、Python packages，並可直接啟動 course exporter；也會檢查 Prometheus、Grafana Local，以及 workshop 需要的 `node_exporter` / `windows_exporter`。每個檢查 cell 通過時都會輸出確認訊息。

如果 notebook 顯示缺少任何項目，回到本頁對應步驟補安裝或啟動即可。

### B. 還沒有 Python / conda 環境，或不確定怎麼安裝

從 Step 1 開始做。完成 Step 1 到 Step 4 後，再回來開 `00-check-your-setup.ipynb` 檢查是否全部就緒。

---

## Step 1. 進入 course repo

所有指令都從 `aiops-anomaly-zero-to-hero` 根目錄執行。

macOS / Linux：

```bash
cd /path/to/aiops-anomaly-zero-to-hero
pwd
```

Windows PowerShell：

```powershell
cd C:\path\to\aiops-anomaly-zero-to-hero
Get-Location
```

---

## Step 2. 建立 Python / conda 環境

依你的作業系統選一份文件：

| 作業系統 | 文件 |
| --- | --- |
| macOS | [01a-setup-macos-python-environment.md](01a-setup-macos-python-environment.md) |
| Linux | [01b-setup-linux-python-environment.md](01b-setup-linux-python-environment.md) |
| Windows | [01c-setup-windows-python-environment.md](01c-setup-windows-python-environment.md) |

完成後，確認你能啟動課程環境：

macOS / Linux：

```bash
conda activate aiops-anomaly-zero-to-hero
jupyter lab labs/
```

Windows PowerShell：

```powershell
conda activate aiops-anomaly-zero-to-hero
jupyter lab labs\
```

你可以使用 JupyterLab、VS Code、PyCharm 或其他支援 Jupyter notebook 的工具。重點是 notebook kernel 要選到 `aiops-anomaly-zero-to-hero`。

---

## Step 3. 安裝並啟動 Prometheus

照這份文件做：

```text
02-install-prometheus.md
```

連結：[02-install-prometheus.md](02-install-prometheus.md)

這一步會讓 Prometheus 抓到課程提供的 synthetic RRD-like metrics。course exporter 的作用是把 repository 裡的 CSV 時間序列資料轉成 Prometheus 可以 scrape 的 `/metrics` 端點；沒有它，Prometheus 會啟動，但查不到課程資料。`00-check-your-setup.ipynb` 會先啟動並檢查 course exporter；你仍需要依此文件安裝並啟動 Prometheus。完成後應能確認：

```text
http://localhost:8000/metrics
http://localhost:9090
```

在 Prometheus 查詢：

```promql
up{job="rrd-exporter"}
```

值應為 `1`。

---

## Step 4. 安裝 Grafana Local 並連接 Prometheus

照這份文件做：

```text
03a-install-grafana-local.md
```

連結：[03a-install-grafana-local.md](03a-install-grafana-local.md)

完成後應能打開：

```text
http://localhost:3000
```

Grafana data source 請連到：

```text
http://localhost:9090
```

---

## Step 5. 跑 setup check notebook

開啟並逐格執行：

```text
labs/getting-started/00-check-your-setup.ipynb
```

你應該看到四個主要檢查通過：

1. Course repo path 通過。
2. Python kernel / packages 通過。
3. Course exporter 通過。
4. Local services 中 `Prometheus`、`Grafana Local` 通過。

如果某一格失敗，notebook 會列出對應安裝指南。先補齊缺項，再重新跑這份 notebook。

請以 notebook 的結果為準。本課程不再提供另一套檢查腳本，避免 terminal Python、conda environment 與 notebook kernel 不一致時產生誤判。

---

## Step 6. 開始 labs

Self-study 開始條件：

- `00-check-your-setup.ipynb` 的 Course repo path 通過。
- Python kernel / packages 通過。
- Course exporter、`Prometheus`、`Grafana Local` 通過。
- `node_exporter` / `windows_exporter` 可以是 `SKIP`。

符合以上條件後，從這裡開始：

```text
labs/self-study/00_observability_stack.ipynb
```

Workshop 開始條件：

- self-study 條件全部通過。
- `node_exporter` 或 `windows_exporter` 也已通過。

符合以上條件後，從這裡開始：

```text
labs/workshop/00_observability_stack_and_promql.ipynb
```

---

## Workshop 延伸：即時 OS metrics

Workshop 若要查自己的電腦網路指標，需要安裝 `node_exporter` 或 `windows_exporter`。

連結：[04-install-node-exporter.md](04-install-node-exporter.md)

Self-study 不需要先做這一步。

---

## 選用：Grafana Cloud

Grafana Cloud 是選用延伸。課程主線只需要 Grafana Local。

連結：[03b-setup-grafana-cloud.md](03b-setup-grafana-cloud.md)

---

## 常見錯誤定位

### `conda` 找不到

先重新開一個 terminal。若仍失敗，回到你的 OS 專用 Python setup 文件：

- [macOS](01a-setup-macos-python-environment.md)
- [Linux](01b-setup-linux-python-environment.md)
- [Windows](01c-setup-windows-python-environment.md)

### notebook 找不到 `aiops-anomaly-zero-to-hero` kernel

先啟用課程環境，再註冊 kernel：

```bash
conda activate aiops-anomaly-zero-to-hero
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero
```

重新整理 notebook，再選 `aiops-anomaly-zero-to-hero` kernel。

### `localhost:8000` 連不上

course exporter 沒有啟動，或啟動後 terminal 被關掉。回到 [02-install-prometheus.md](02-install-prometheus.md)，確認 `python infra/rrd_exporter.py` 還在執行。

### `localhost:9090` 連不上

Prometheus 沒有啟動，或 9090 port 被其他程序佔用。回到 [02-install-prometheus.md](02-install-prometheus.md) 查看 Prometheus 啟動方式。

### Grafana `Save & test` 失敗

Grafana data source URL 應填：

```text
http://localhost:9090
```

不要填 `http://localhost:3000`。`3000` 是 Grafana 自己，`9090` 才是 Prometheus。

---

## Conda environment files

大多數學員不需要手動選這些檔案；setup guide 或 bootstrap script 會處理。

| 檔案 | 用途 |
| --- | --- |
| `environment.yml` | 預設跨平台版本 |
| `environments/environment.macos.yml` | macOS 版本 |
| `environments/environment.linux.yml` | Linux 版本 |
| `environments/environment.windows.yml` | Windows 版本 |

三個平台檔都建立同一個 conda environment：`aiops-anomaly-zero-to-hero`。
