# Lab 03–05 教材更新與 Docker Compose 安裝指南

這份指南適用於已經完成原始課程 setup、現在要加入 Lab 03、Lab 04 與 Lab 05 的學員。請先把新教材放到正確位置，再安裝 Lab 05 需要的 Docker。

所有指令都要從教材根目錄執行，也就是同時看得到 `labs/`、`data/`、`infra/` 與 `environments/` 的那一層。

## 這次新增什麼？

| Lab | Notebook | 必要資料 | 新安裝需求 |
| --- | --- | --- | --- |
| Lab 03 | `03_spc_anomaly_detection.ipynb` | 3 份 `lab03_*.csv` | 無；沿用既有 Conda environment |
| Lab 04 | `04_ml_anomaly_detection.ipynb` | 3 份 `lab04_*.csv` | 無；`scikit-learn` 已包含在既有 environment |
| Lab 05 | `05_production_alert_pipeline.ipynb`、`lab05_control.py` | 2 份 `lab05_*.csv`、完整 `infra/lab05/` | Docker Engine／Docker Desktop 與 Docker Compose v2 |

Lab 03 與 Lab 04 不需要另外安裝 Python package。Lab 05 的 notebook 可以離線閱讀，但實作 Prometheus、Alertmanager、Grafana、replayer 與 receiver 時必須啟動 Docker Compose。

## 下載並放置新檔案

```text
<教材根目錄>/
├── labs/
│   └── workshop/
│       ├── 03_spc_anomaly_detection.ipynb
│       ├── 04_ml_anomaly_detection.ipynb
│       ├── 05_production_alert_pipeline.ipynb
│       └── lab05_control.py
├── data/
│   └── synthetic/
│       ├── lab03_reference.csv
│       ├── lab03_spc_scenarios.csv
│       ├── lab03_spc_events.csv
│       ├── lab04_reference.csv
│       ├── lab04_multivariate_scenarios.csv
│       ├── lab04_multivariate_events.csv
│       ├── lab05_replay_metrics.csv
│       └── lab05_event_catalog.csv
└── infra/
    └── lab05/
        ├── compose.yaml
        ├── .env.example
        ├── prometheus/
        ├── alertmanager/
        ├── grafana/
        ├── replayer/
        └── receiver/
```

## 先檢查檔案與 Python environment

啟用原本的課程 environment：

```bash
conda activate aiops-anomaly-zero-to-hero
```

Windows PowerShell、macOS terminal 與 Linux shell 都使用同一條 Conda 指令。再從教材根目錄執行下面的跨平台檔案檢查：

```bash
python -c "from pathlib import Path; paths=['labs/workshop/03_spc_anomaly_detection.ipynb','labs/workshop/04_ml_anomaly_detection.ipynb','labs/workshop/05_production_alert_pipeline.ipynb','labs/workshop/lab05_control.py','data/synthetic/lab03_reference.csv','data/synthetic/lab03_spc_scenarios.csv','data/synthetic/lab03_spc_events.csv','data/synthetic/lab04_reference.csv','data/synthetic/lab04_multivariate_scenarios.csv','data/synthetic/lab04_multivariate_events.csv','data/synthetic/lab05_replay_metrics.csv','data/synthetic/lab05_event_catalog.csv','infra/lab05/compose.yaml']; missing=[p for p in paths if not Path(p).exists()]; print('PASS: required files found' if not missing else 'Missing:\n'+'\n'.join(missing)); raise SystemExit(bool(missing))"
```

看到 `PASS: required files found` 才繼續。若需要重新檢查原始課程環境，也可以逐格執行 [`00-check-your-setup.ipynb`](00-check-your-setup.ipynb)。

## 安裝 Docker 與 Compose

本課程使用 Compose v2；正確指令是 `docker compose`，兩個字之間有空格。安裝 Docker Desktop 時已包含 Docker Engine、Docker CLI 與 Compose，不必再單獨安裝 Compose。

### Windows

1. 確認 Windows virtualization 與 WSL 2 可用。若尚未安裝 WSL，可參考 Microsoft 提供的 [`wsl --install` 指南](https://learn.microsoft.com/windows/wsl/install)。
2. 依照 [Docker Desktop for Windows 官方安裝指南](https://docs.docker.com/desktop/setup/install/windows-install/)下載並安裝 Docker Desktop。
3. 啟動 Docker Desktop，等候介面顯示 Docker Engine 正在執行。
4. 本 Lab 使用 Linux container images；Docker Desktop 必須保持在 Linux containers 模式。
5. 重新開啟 PowerShell，再執行本頁的共同驗收指令。

### macOS

1. 在 Apple menu 的 `About This Mac` 確認晶片是 Apple silicon 或 Intel；也可在 terminal 執行 `uname -m`，`arm64` 代表 Apple silicon、`x86_64` 代表 Intel。
2. 從 [Docker Desktop for Mac 官方安裝指南](https://docs.docker.com/desktop/setup/install/mac-install/)選擇正確晶片版本。
3. 安裝並啟動 Docker Desktop，等候 Docker Engine ready，再執行本頁的共同驗收指令。

### Linux

Linux 可安裝 Docker Desktop，也可以直接安裝 Docker Engine。課堂環境建議依自己的 distribution 使用 Docker Engine 官方 repository：

- [Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Debian](https://docs.docker.com/engine/install/debian/)
- [Fedora](https://docs.docker.com/engine/install/fedora/)
- [CentOS](https://docs.docker.com/engine/install/centos/)
- [RHEL](https://docs.docker.com/engine/install/rhel/)
- [其他 Linux distributions](https://docs.docker.com/engine/install/)

依官方頁面的 `Install using the apt/rpm repository` 步驟安裝 Docker Engine、Docker CLI、Buildx 與 Compose plugin。若 Docker Engine 已存在但 `docker compose version` 失敗，請依 [Compose plugin 官方安裝指南](https://docs.docker.com/compose/install/linux/)補裝 Compose plugin。

`lab05_control.py` 會直接呼叫 `docker`，因此目前帳號必須能在不加 `sudo` 的情況下執行 `docker info`。需要時依 [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)設定 Docker group，登出再登入後重新驗收。請注意：Docker group 具有 root-level privileges，只應授權可信任的本機帳號。

## 共同安裝驗收

先確認 Docker Desktop 或 Linux Docker daemon 已啟動，再從教材根目錄逐條執行：

```bash
docker --version
docker compose version
docker info
docker compose -f infra/lab05/compose.yaml config
```

預期結果：

- `docker --version` 顯示 Docker version。
- `docker compose version` 顯示 Docker Compose version。
- `docker info` 顯示 Client 與 Server 資訊，而不是 daemon connection error。
- 最後一條指令輸出展開後的 Compose configuration，且沒有找不到檔案或 YAML error。

第一次啟動 Lab 05 時需要網路下載 container images，請在上課前完成。
