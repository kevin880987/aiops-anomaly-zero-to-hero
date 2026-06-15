# Python 環境設定 — Windows

## 前置條件

- Windows 10 21H2 以上，或 Windows 11
- PowerShell 5.1 以上（Windows 內建版本即可）

`winget` 與 Python 3.10+ 若尚未安裝，腳本會自動處理。

## 設定三個值

執行前，把下列範例值換成自己的名稱：

| 設定 | 用途 | 範例 |
|---|---|---|
| `Name` | Jupyter kernel 清單中顯示的名稱 | `my-aiops-project` |
| `VenvDir` | Python 套件安裝位置 | `$HOME\.venvs\my-aiops-project` |
| `CacheDir` | Matplotlib / Fontconfig 暫存檔位置 | `$HOME\.cache\my-aiops-project` |

## 步驟

### 1. 進入專案根目錄

```powershell
cd aiops-anomaly-detection
```

### 2. 建立 Python 環境

```powershell
powershell -ExecutionPolicy Bypass -File getting-started/scripts/bootstrap_windows.ps1 `
  -Name "my-aiops-project" `
  -VenvDir "$HOME\.venvs\my-aiops-project" `
  -CacheDir "$HOME\.cache\my-aiops-project"
```

腳本依序執行：檢查 Python 3.10+ → 必要時透過 `winget` 安裝 → 建立虛擬環境 → 安裝套件 → 註冊 Jupyter kernel。

### 3. 啟動 JupyterLab

```powershell
py getting-started/scripts/start_jupyter.py `
  --venv-dir "$HOME\.venvs\my-aiops-project" `
  --cache-dir "$HOME\.cache\my-aiops-project" `
  --jupyter-dir "notebooks"
```

瀏覽器會自動開啟 JupyterLab。依序執行：

1. `Notebook1_Time_Series_Features.ipynb`
2. `Notebook2_Baseline_Anomaly_Detection.ipynb`

## 環境變數（選用）

在固定工作站重複使用同一組設定時，可預先設定：

```powershell
$env:AIOPS_PROJECT_NAME = "my-aiops-project"
$env:AIOPS_VENV_DIR     = "$HOME\.venvs\my-aiops-project"
$env:AIOPS_CACHE_DIR    = "$HOME\.cache\my-aiops-project"
$env:AIOPS_JUPYTER_DIR  = "notebooks"
```

| 環境變數 | 對應腳本參數 |
|---|---|
| `AIOPS_PROJECT_NAME` | `-Name` |
| `AIOPS_VENV_DIR` | `-VenvDir` |
| `AIOPS_CACHE_DIR` | `-CacheDir` |
| `AIOPS_JUPYTER_DIR` | 無，僅用於 `start_jupyter.py` 的 `--jupyter-dir` |

## Notebook 工具選項

JupyterLab 是預設路徑，但任何支援 Jupyter kernel 的工具都可以使用：

- [JupyterLab](https://jupyter.org/) — 本指南的預設。
- [Visual Studio Code](https://code.visualstudio.com/) — 開啟 `.ipynb`，在右上角選 `Python (my-aiops-project)`。
- [PyCharm](https://www.jetbrains.com/pycharm/) — Professional 版支援 Jupyter notebooks。

## 常見問題

**bootstrap 和 start 要分別執行幾次？**
`bootstrap_windows.ps1` 通常只執行一次（建立環境）。之後每次上課，只需執行 `start_jupyter.py`。

**可以直接複製指令嗎？**
可以，但須將所有 `my-aiops-project` 替換為自己的名稱，包含路徑中的部分。

**PowerShell 顯示執行原則錯誤怎麼辦？**
指令已加入 `-ExecutionPolicy Bypass`，應可直接執行。若仍出錯，以系統管理員身分開啟 PowerShell 再試一次。
