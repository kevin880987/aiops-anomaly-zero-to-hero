# Python 環境設定

三個平台共用這一頁。每一步都先列 macOS / Linux，再列 Windows PowerShell，只跑自己作業系統的那一塊。

## 前置條件

| 作業系統 | 需要 |
| --- | --- |
| macOS | macOS 12 Monterey 以上，終端機（Terminal 或 iTerm2） |
| Linux | Ubuntu、Debian、Fedora、Rocky Linux 等發行版，Bash terminal |
| Windows | Windows 10 21H2 以上或 Windows 11，PowerShell 5.1 以上（內建版本即可） |

本課程使用 conda 管理 Python 套件。若尚未安裝 conda，請先安裝 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)。Linux 發行版很多，套件管理器各不相同，所以 Linux 這一端請照 Miniconda 官方頁面的步驟自己裝。

## 步驟

### 1. 進入專案根目錄

macOS / Linux：

```bash
cd aiops-anomaly-zero-to-hero
```

Windows PowerShell：

```powershell
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

環境檔按平台分成三份，跑自己那一份。三份建立的是同一個 conda environment：`aiops-anomaly-zero-to-hero`。

macOS：

```bash
conda env create -f environments/environment.macos.yml
```

Linux：

```bash
conda env create -f environments/environment.linux.yml
```

Windows PowerShell：

```powershell
conda env create -f environments\environment.windows.yml
```

環境已存在時改用更新指令，把上面的 `create` 換成 `update -n aiops-anomaly-zero-to-hero`，結尾加 `--prune`：

```bash
conda env update -n aiops-anomaly-zero-to-hero -f environments/environment.macos.yml --prune
```

啟用環境，三個平台指令相同：

```bash
conda activate aiops-anomaly-zero-to-hero
```

### 3. 開啟 labs

用你慣用的 notebook 工具開啟 `labs/getting-started/00-check-your-setup.ipynb`（Windows 是 `labs\getting-started\00-check-your-setup.ipynb`），kernel 選課程環境，然後逐格執行。這份 notebook 是最終檢查入口；若缺少任何項目，它會指向對應安裝指南。

## Labs 工具選項

工具只要連得上上一步啟用的 conda 環境就可以用：

- [Visual Studio Code](https://code.visualstudio.com/)，安裝 Python 與 Jupyter 擴充套件後直接開啟 `.ipynb`。
- [PyCharm](https://www.jetbrains.com/pycharm/)，Professional 版內建 notebook 支援。
- [JupyterLab](https://jupyter.org/)，`conda install -n aiops-anomaly-zero-to-hero jupyterlab` 後執行 `jupyter lab labs/`。

## 常見問題

**conda activate 沒有作用？**（macOS / Linux）
執行 `conda init zsh` 或 `conda init bash`，重新開啟終端機，再試一次。

**已安裝 conda，但終端機找不到？**（macOS / Linux）
重新開啟終端機後再執行。若仍失敗，依你的安裝位置執行 conda init，例如：

```bash
/opt/miniconda3/bin/conda init zsh
```

**Miniconda 安裝完成但 PowerShell 仍找不到 conda？**（Windows）
關閉 PowerShell，重新開啟後再執行。Windows 安裝程式通常需要新的終端機才會讀到更新後的 PATH。

**`conda activate` 出現執行原則錯誤（Cannot be loaded because running scripts is disabled）？**（Windows）
PowerShell 預設限制執行腳本。請以一般使用者身份執行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

確認後重新執行 `conda activate aiops-anomaly-zero-to-hero`。

**指令顯示找不到環境檔？**
請確認你目前在專案根目錄，也就是可以看到 `environments/` 與 `labs/` 的那一層。

**notebook 的 kernel 選單裡看不到課程環境？**
編輯器通常會自己列出 conda environment。找不到時先啟用環境，把它註冊成一個具名 kernel：

```bash
conda activate aiops-anomaly-zero-to-hero
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

重新載入編輯器的 kernel 選單，再選 `Python (aiops-anomaly-zero-to-hero)`。

**環境要怎麼完全刪除重建？**

```bash
conda env remove -n aiops-anomaly-zero-to-hero
conda env create -f environments/environment.macos.yml
```

Windows 的環境檔路徑是 `environments\environment.windows.yml`，Linux 是 `environments/environment.linux.yml`。
