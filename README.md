# AIOps Anomaly Detection: Zero to Hero

這是一套從網路 telemetry、可觀測性到 AIOps 決策支援的實作課程。學員會建立 Prometheus 與 Grafana 環境，理解 RRD/SNMP-like metrics，再完成特徵工程、異常偵測、告警降噪、預測與根因分析。

```text
Network telemetry
  -> Prometheus and Grafana
  -> time-series features
  -> anomaly detection
  -> alert reduction
  -> forecasting
  -> root-cause analysis
  -> operational action
```

核心路徑不要求雲端帳號、Kubernetes 或 Python package 開發經驗。初學者只需要依照設定指南建立 conda 環境，安裝本機 Prometheus 與 Grafana，接著從 labs 開始操作。

## 立即開始

### 路徑一：從初學者設定指南開始

第一次使用請先閱讀 [`labs/getting-started/README.md`](labs/getting-started/README.md)。如果你已經完成環境設定，直接看 [`labs/README.md`](labs/README.md) 選擇工作坊短版或完整自學版。若要先理解整份教材的對象、學習成果、資料流與教學節奏，請看 [`COURSE_GUIDE.md`](COURSE_GUIDE.md)。

設定指南會帶你完成三件事：

1. 使用 conda 建立 Python 與 JupyterLab 環境。
2. 依作業系統安裝 Prometheus。
3. 依作業系統安裝 Grafana，並連接 Prometheus。

macOS 可在 repository 根目錄執行：

```bash
bash labs/getting-started/scripts/bootstrap_macos.sh
```

Windows 可在 repository 根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File labs\getting-started\scripts\bootstrap_windows.ps1
```

兩個腳本都會先檢查現有 conda 環境；若已符合課程需求，會跳過更新。若只想準備環境、不立刻開啟 JupyterLab，macOS 加上 `--no-launch`，Windows 加上 `-NoLaunch`。

### 路徑二：開啟 labs

設定完成後，在 JupyterLab 依序執行 `labs/` 中的課程檔案。若要手動啟動：

```bash
conda activate aiops-anomaly-zero-to-hero
jupyter lab labs
```

## Labs 路徑

本 repository 提供兩條 notebook 路徑：

- `labs/hands-on/`：工作坊短版，聚焦可觀測性、特徵工程、異常偵測與 RCA capstone。
- `labs/full-course/`：完整自學版，從資料模擬一路做到部署檢查。

完整自學版建議依序執行：

1. `data/synthetic/simulator_rrd_metrics.ipynb`
2. `labs/full-course/00_observability_stack.ipynb`
3. `labs/full-course/01_time_series_features.ipynb`
4. `labs/full-course/02_baseline_anomaly_detection.ipynb`
5. `labs/full-course/03_spc_anomaly_detection.ipynb`
6. `labs/full-course/04_ml_anomaly_detection.ipynb`
7. `labs/full-course/05_alert_reduction.ipynb`
8. `labs/full-course/06_forecasting.ipynb`
9. `labs/full-course/07_root_cause_analysis.ipynb`
10. `labs/full-course/08_deploy_to_production.ipynb`

## 課程架構

| 路徑 | 學習成果 | 目前狀態 |
| --- | --- | --- |
| `labs/getting-started/` | 建立 conda 環境，安裝 Prometheus、Grafana 與 OS exporter | 完整 |
| `labs/hands-on/` | 工作坊短版，使用即時 Prometheus 指標完成核心 AIOps 流程 | 完整 |
| `labs/full-course/` | 完整自學版，使用 synthetic data 重建 features、alerts、forecast 與 RCA outputs | 完整 |

## Repository 結構

```text
.
├── environment.yml              # conda 課程環境
├── COURSE_GUIDE.md              # 教材總覽、學習成果、路線與檢核方式
├── labs/                        # AIOps 教學 labs
│   ├── getting-started/         # 初學者設定指南與啟動腳本
│   ├── full-course/             # 完整自學版 notebooks
│   └── hands-on/                # 工作坊短版 notebooks
├── data/                        # synthetic、sample、processed data
├── prometheus/                  # Prometheus 設定範例
├── grafana/                     # Grafana datasource 與 dashboard 設定範例
└── exporter.py                  # CSV-to-Prometheus metrics exporter
```

Docker 不在本教學主路徑內。依照 `labs/getting-started/` 完成 conda 與本機監控工具安裝即可開始。

Prometheus 設定檔分平台提供：macOS / Linux 使用 `prometheus/prometheus.yml`，Windows 使用 `prometheus/prometheus.windows.yml`。Python 環境、notebooks、dashboard 與 synthetic data 都隨 repository 一起提供；clone 後不需要複製本機私有檔案。

## 資料

```text
data/
├── synthetic/   # 可由 simulator 重建的 RRD-like metrics
├── sample/      # LibreNMS/RRDTool sample data
└── processed/   # labs 產出的 features、alerts、forecast 與 RCA 結果
```

讀取 `.rrd` sample 需要系統安裝 RRDtool。macOS 可執行：

```bash
brew install rrdtool
```

## 課程設計原則

- 每個 lab 都要有明確輸入、操作、驗證方法、預期結果與清除步驟。
- 核心路徑先使用本機環境，Kubernetes、OpenTelemetry 與雲端部署列為進階內容。
- 故障情境必須可重現，不能只展示完成後的 dashboard。
- dashboard、告警與模型輸出必須能追溯到原始 telemetry。
- 生成式 AI 只能協助解釋有證據的訊號，不替代監控資料或驗證程序。

本課程參考 [grafana-zero-to-hero](https://github.com/blueswen/grafana-zero-to-hero) 與 [observability-zero-to-hero](https://github.com/iam-veeramalla/observability-zero-to-hero) 的課程組織方式，但範例、資料、程式與練習均在本 repository 中獨立設計。

## License

[MIT](LICENSE)
