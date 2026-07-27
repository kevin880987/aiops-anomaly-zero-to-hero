# Python 環境設定

## 前置條件

| 作業系統 | 需求 |
| --- | --- |
| macOS | macOS 12 Monterey 以上，終端機（Terminal 或 iTerm2） |
| Linux | Ubuntu、Debian、Fedora、Rocky Linux 等發行版，Bash terminal |
| Windows | Windows 10 21H2 以上或 Windows 11，PowerShell 5.1 以上（內建版本即可） |

本課程使用 conda 管理 Python 套件，Python 直譯器由 conda 環境提供，不需要另外安裝系統 Python。尚未安裝 conda 的話，先照官方安裝指南完成安裝再回來：

- [Miniconda 安裝指南](https://www.anaconda.com/docs/getting-started/miniconda/install)（本課程建議，體積小）
- [conda 官方安裝文件](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html)（三個平台的完整說明）
- [Python 官方下載頁](https://www.python.org/downloads/)（不使用 conda 時的來源）

## 步驟

### 1. 進入專案根目錄

```bash
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

環境檔按平台分成三份，建立出來的是同一個 conda environment：`aiops-anomaly-zero-to-hero`。執行你這個作業系統對應的那一份：

| 作業系統 | 環境檔 |
| --- | --- |
| macOS | `environments/environment.macos.yml` |
| Linux | `environments/environment.linux.yml` |
| Windows | `environments\environment.windows.yml` |

```bash
conda env create -f environments/environment.macos.yml
```

環境已存在時改用更新指令，`create` 換成 `update -n aiops-anomaly-zero-to-hero`，結尾加 `--prune`：

```bash
conda env update -n aiops-anomaly-zero-to-hero -f environments/environment.macos.yml --prune
```

啟用環境：

```bash
conda activate aiops-anomaly-zero-to-hero
```

### 3. 開啟 labs

用你慣用的 IDE 或 notebook 工具開啟 `labs/getting-started/00-check-your-setup.ipynb`，kernel 選擇課程環境，然後逐格執行。這份 notebook 是最終檢查入口，缺少任何項目時它會指向對應的安裝指南。

## IDE 與 notebook 工具

工具只要能連上一步啟用的 conda 環境就可以用。三者的官方安裝說明：

| 工具 | 安裝指南 | 開啟 notebook 的方式 |
| --- | --- | --- |
| Visual Studio Code | [Setup overview](https://code.visualstudio.com/docs/setup/setup-overview) | 安裝 Python 與 Jupyter 擴充套件後直接開啟 `.ipynb`，做法見 [Jupyter Notebooks in VS Code](https://code.visualstudio.com/docs/datascience/jupyter-notebooks) |
| PyCharm | [Installation guide](https://www.jetbrains.com/help/pycharm/installation-guide.html) | Professional 版內建 notebook 支援 |
| JupyterLab | [Installation](https://jupyterlab.readthedocs.io/en/stable/getting_started/installation.html) | `conda install -n aiops-anomaly-zero-to-hero jupyterlab` 之後執行 `jupyter lab labs/` |

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

**notebook 的 kernel 選單列不出課程環境？**
編輯器通常會自己列出 conda environment。找不到時先啟用環境，把它註冊成一個具名 kernel：

```bash
conda activate aiops-anomaly-zero-to-hero
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

重新載入編輯器的 kernel 選單，再選擇 `Python (aiops-anomaly-zero-to-hero)`。

**環境要怎麼完全刪除重建？**

```bash
conda env remove -n aiops-anomaly-zero-to-hero
conda env create -f environments/environment.macos.yml
```

環境檔路徑換成上表你那一列。
