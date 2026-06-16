# Python 環境設定 — Windows

## 前置條件

- Windows 10 21H2 以上，或 Windows 11
- PowerShell 5.1 以上（Windows 內建版本即可）

本課程使用 conda 管理 Python 套件。Miniconda 若尚未安裝，腳本會優先透過 `winget` 自動安裝；若 `winget` 不可用，文件會引導手動安裝。

## 步驟

### 1. 進入專案根目錄

```powershell
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

```powershell
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1
```

腳本依序執行：

1. 檢查 conda；若未安裝，透過 `winget` 安裝 Miniconda。
2. 檢查 `environment.yml` 與 `labs\` 是否存在。
3. 建立 `aiops-anomaly-zero-to-hero` 環境；若環境已存在且符合需求，直接跳過更新。
4. 啟動 JupyterLab，開啟 `labs\` 目錄。

只建立環境、不立刻開啟 JupyterLab：

```powershell
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1 -NoLaunch
```

強制依照 `environment.yml` 更新環境：

```powershell
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1 -Update
```

### 3. 之後每次啟動

```powershell
conda activate aiops-anomaly-zero-to-hero
jupyter lab labs\
```

## Labs 工具選項

JupyterLab 是預設路徑，但任何支援 Jupyter kernel 的工具都可以使用：

- [JupyterLab](https://jupyter.org/) — 本指南的預設。
- [Visual Studio Code](https://code.visualstudio.com/) — 開啟 `.ipynb`，在右上角的 kernel 選單選擇 `aiops-anomaly-zero-to-hero`。
- [PyCharm](https://www.jetbrains.com/pycharm/) — Professional 版支援 Jupyter labs。

## 常見問題

**PowerShell 顯示執行原則錯誤？**
指令已加入 `-ExecutionPolicy Bypass`，應可直接執行。若仍出錯，以系統管理員身分開啟 PowerShell 再試一次。

**腳本顯示 `environment.yml not found`？**
請確認你目前在專案根目錄，也就是可以看到 `environment.yml` 與 `labs\` 的那一層。

**winget 找不到 Miniconda？**
手動下載安裝：[https://docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html)，安裝後重新執行腳本。

**Miniconda 安裝完成但腳本仍找不到 conda？**
關閉 PowerShell，重新開啟後再執行。Windows 安裝程式通常需要新的終端機才會讀到更新後的 PATH。

**環境已存在想更新套件版本？**

```powershell
conda env update -n aiops-anomaly-zero-to-hero -f environment.yml --prune
```

**環境要怎麼完全刪除重建？**

```powershell
conda env remove -n aiops-anomaly-zero-to-hero
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1
```
