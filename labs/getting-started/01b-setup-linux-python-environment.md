# Python 環境設定 — Linux

## 前置條件

- Linux 發行版，例如 Ubuntu、Debian、Fedora 或 Rocky Linux
- Bash terminal

本課程使用 conda 管理 Python 套件。若尚未安裝 conda，請先安裝 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)。Linux 發行版很多，本課程不假設你使用哪一個套件管理器，因此不提供自動安裝 conda 的 Linux 腳本。

## 步驟

### 1. 進入專案根目錄

```bash
cd aiops-anomaly-zero-to-hero
```

### 2. 建立 conda 環境

```bash
conda env create -f environments/environment.linux.yml
conda activate aiops-anomaly-zero-to-hero
```

如果環境已存在，改用更新指令：

```bash
conda env update -n aiops-anomaly-zero-to-hero -f environments/environment.linux.yml --prune
conda activate aiops-anomaly-zero-to-hero
```

### 3. 註冊 Jupyter kernel

讓 JupyterLab 能在 kernel 選單中找到這個環境：

```bash
python -m ipykernel install --user --name aiops-anomaly-zero-to-hero --display-name "Python (aiops-anomaly-zero-to-hero)"
```

### 4. 之後每次啟動

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
執行 `conda init bash`，重新開啟 terminal，再試一次。

**指令顯示 `environment.yml not found`？**
請確認你目前在專案根目錄，也就是可以看到 `environment.yml` 與 `labs/` 的那一層。

**環境已存在想更新套件版本？**

```bash
conda env update -n aiops-anomaly-zero-to-hero -f environments/environment.linux.yml --prune
```

**環境要怎麼完全刪除重建？**

```bash
conda env remove -n aiops-anomaly-zero-to-hero
conda env create -f environments/environment.linux.yml
```
