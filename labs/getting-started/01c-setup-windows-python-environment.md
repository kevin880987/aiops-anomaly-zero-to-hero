# Python 環境設定 — Windows

## 前置條件

- Windows 10 21H2 以上，或 Windows 11
- PowerShell 5.1 以上（Windows 內建版本即可）

本課程使用 conda 管理 Python 套件。若尚未安裝 conda，請先安裝 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)。

## 步驟

### 1. 進入專案根目錄

```powershell
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

```powershell
conda env create -f environments\environment.windows.yml
```

如果環境已存在，改用更新指令：

```powershell
conda env update -n aiops-anomaly-zero-to-hero -f environments\environment.windows.yml --prune
```

啟用環境：

```powershell
conda activate aiops-anomaly-zero-to-hero
```

### 3. 啟動 JupyterLab

```powershell
jupyter lab labs\
```

打開 `labs\getting-started\00-check-your-setup.ipynb`，逐格執行。這份 notebook 是最終檢查入口；若缺少任何項目，它會指向對應安裝指南。

## Labs 工具選項

JupyterLab 是預設路徑，但任何支援 Jupyter kernel 的工具都可以使用：

- [JupyterLab](https://jupyter.org/) — 本指南的預設。
- [Visual Studio Code](https://code.visualstudio.com/) — 開啟 `.ipynb`，在右上角的 kernel 選單選擇 `aiops-anomaly-zero-to-hero`。
- [PyCharm](https://www.jetbrains.com/pycharm/) — Professional 版支援 Jupyter labs。

## 常見問題

**指令顯示 `environment.yml not found`？**
請確認你目前在專案根目錄，也就是可以看到 `environment.yml` 與 `labs\` 的那一層。

**Miniconda 安裝完成但 PowerShell 仍找不到 conda？**
關閉 PowerShell，重新開啟後再執行。Windows 安裝程式通常需要新的終端機才會讀到更新後的 PATH。

**環境已存在想更新套件版本？**

```powershell
conda env update -n aiops-anomaly-zero-to-hero -f environments\environment.windows.yml --prune
```

**環境要怎麼完全刪除重建？**

```powershell
conda env remove -n aiops-anomaly-zero-to-hero
conda env create -f environments\environment.windows.yml
```
