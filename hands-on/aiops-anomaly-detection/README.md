# Week 4 實作 — AIOps 異常偵測

## 啟動步驟

如果你是第一次使用 Python / Jupyter，先閱讀 [getting-started/README.md](getting-started/README.md)。設定腳本不內建專案名稱或使用者目錄；你需要明確提供 project name、environment directory、cache directory。

macOS 範例。先進入 `aiops-anomaly-detection` 根目錄：

```bash
cd aiops-anomaly-detection
```

再執行：

```bash
bash getting-started/scripts/bootstrap_macos.sh \
  --name "my-aiops-project" \
  --venv-dir "$HOME/.venvs/my-aiops-project" \
  --cache-dir "$HOME/.cache/my-aiops-project"

python3 getting-started/scripts/start_jupyter.py \
  --venv-dir "$HOME/.venvs/my-aiops-project" \
  --cache-dir "$HOME/.cache/my-aiops-project" \
  --jupyter-dir "notebooks"
```

Windows PowerShell 範例。先進入 `aiops-anomaly-detection` 根目錄：

```powershell
cd aiops-anomaly-detection
```

再執行：

```powershell
powershell -ExecutionPolicy Bypass -File getting-started/scripts/bootstrap_windows.ps1 `
  -Name "my-aiops-project" `
  -VenvDir "$HOME\.venvs\my-aiops-project" `
  -CacheDir "$HOME\.cache\my-aiops-project"

py getting-started/scripts/start_jupyter.py `
  --venv-dir "$HOME\.venvs\my-aiops-project" `
  --cache-dir "$HOME\.cache\my-aiops-project" `
  --jupyter-dir "notebooks"
```

## 執行順序

1. `Notebook1_Time_Series_Features.ipynb` — 特徵工程
2. `Notebook2_Baseline_Anomaly_Detection.ipynb` — 異常偵測

## 目錄結構

```text
aiops-anomaly-detection/
├── getting-started/
│   ├── README.md              ← macOS / Windows 初學者設定
│   └── scripts/
│       ├── bootstrap_macos.sh     ← macOS Python 檢查 / 安裝入口
│       ├── bootstrap_windows.ps1  ← Windows Python 檢查 / 安裝入口
│       ├── setup.py               ← 跨平台環境建立與 kernel 註冊
│       └── start_jupyter.py       ← 跨平台 JupyterLab 啟動
├── notebooks/
│   ├── Notebook1_...ipynb   ← 時間序列特徵工程
│   └── Notebook2_...ipynb   ← Baseline Anomaly Detection
└── README.md
```

資料來自上層 `data/synthetic/`，不需要額外下載。
