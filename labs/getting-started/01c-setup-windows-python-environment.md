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

### 3. 註冊 Jupyter kernel

讓 notebook 工具在 kernel 選單中找到這個環境：

```powershell
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

### 4. 開啟 labs

用你慣用的 notebook 工具開啟 `labs\getting-started\00-check-your-setup.ipynb`，kernel 選 `Python (aiops-anomaly-zero-to-hero)`，然後逐格執行。這份 notebook 是最終檢查入口；若缺少任何項目，它會指向對應安裝指南。

## Labs 工具選項

只要工具連得上第 3 步註冊的 kernel 就可以用：

- [Visual Studio Code](https://code.visualstudio.com/)，安裝 Python 與 Jupyter 擴充套件後直接開啟 `.ipynb`。
- [PyCharm](https://www.jetbrains.com/pycharm/)，Professional 版內建 notebook 支援。
- [JupyterLab](https://jupyter.org/)，`conda install -n aiops-anomaly-zero-to-hero jupyterlab` 後執行 `jupyter lab labs\`。

## 常見問題

**指令顯示找不到環境檔？**
請確認你目前在專案根目錄，也就是可以看到 `environments\` 與 `labs\` 的那一層。

**Miniconda 安裝完成但 PowerShell 仍找不到 conda？**
關閉 PowerShell，重新開啟後再執行。Windows 安裝程式通常需要新的終端機才會讀到更新後的 PATH。

**`conda activate` 執行後出現執行原則錯誤（Cannot be loaded because running scripts is disabled）？**
PowerShell 預設限制執行腳本。請以一般使用者身份執行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

確認後重新執行 `conda activate aiops-anomaly-zero-to-hero`。

**環境已存在想更新套件版本？**

```powershell
conda env update -n aiops-anomaly-zero-to-hero -f environments\environment.windows.yml --prune
```

**環境要怎麼完全刪除重建？**

```powershell
conda env remove -n aiops-anomaly-zero-to-hero
conda env create -f environments\environment.windows.yml
```
