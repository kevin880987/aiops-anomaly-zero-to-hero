# Python 環境設定 — macOS

## 前置條件

- macOS 12 Monterey 以上
- 終端機（Terminal 或 iTerm2）

本課程使用 conda 管理 Python 套件。Miniconda 若尚未安裝，腳本會自動下載並安裝到 `~/miniconda3`。

## 步驟

### 1. 進入專案根目錄

```bash
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

```bash
bash labs/getting-started/scripts/bootstrap_macos.sh
```

腳本依序執行：

1. 檢查 conda；若未安裝，自動安裝 Miniconda。
2. 檢查 `environment.yml` 與 `labs/` 是否存在。
3. 建立 `aiops-anomaly-zero-to-hero` 環境；若環境已存在且符合需求，直接跳過更新。
4. 啟動 JupyterLab，開啟 `labs/` 目錄。

只建立環境、不立刻開啟 JupyterLab：

```bash
bash labs/getting-started/scripts/bootstrap_macos.sh --no-launch
```

強制依照 macOS environment YAML 更新環境：

```bash
bash labs/getting-started/scripts/bootstrap_macos.sh --update
```

### 3. 之後每次啟動

```bash
conda activate aiops-anomaly-zero-to-hero
jupyter lab labs/
```

## Labs 工具選項

JupyterLab 是預設路徑，但任何支援 Jupyter kernel 的工具都可以使用：

- [JupyterLab](https://jupyter.org/) — 本指南的預設。
- [Visual Studio Code](https://code.visualstudio.com/) — 開啟 `.ipynb`，在右上角的 kernel 選單選擇 `aiops-anomaly-zero-to-hero`。
- [PyCharm](https://www.jetbrains.com/pycharm/) — Professional 版支援 Jupyter labs。

## 常見問題

**conda activate 沒有作用？**
執行 `conda init zsh`（或 `conda init bash`），重新開啟終端機，再試一次。

**腳本顯示 `environment.yml not found`？**
請確認你目前在專案根目錄，也就是可以看到 `environment.yml` 與 `labs/` 的那一層。

**已安裝 conda，但腳本仍找不到？**
重新開啟終端機後再執行。若仍失敗，先執行：

```bash
~/miniconda3/bin/conda init zsh
```

**環境已存在想更新套件版本？**

```bash
conda env update -n aiops-anomaly-zero-to-hero -f environments/environment.macos.yml --prune
```

**環境要怎麼完全刪除重建？**

```bash
conda env remove -n aiops-anomaly-zero-to-hero
bash labs/getting-started/scripts/bootstrap_macos.sh
```
