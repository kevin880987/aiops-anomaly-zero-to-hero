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

核心路徑不要求雲端帳號或 Kubernetes。Docker lab、Python package、notebooks、資料與測試均收錄在同一個 repository。

## 立即開始

### 路徑一：啟動即時監控環境

安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 後，在 repository 根目錄執行：

```bash
docker compose up --build -d
```

開啟：

- Grafana: <http://localhost:3000>，本機課程帳號為 `admin` / `admin`
- Prometheus: <http://localhost:9090>
- RRD replay metrics: <http://localhost:8000/metrics>

Grafana 已 provision `Network Interface Monitoring` dashboard。完整操作與驗證步驟見 [`labs/01-observability-foundation/README.md`](labs/01-observability-foundation/README.md)。

停止環境：

```bash
docker compose down
```

刪除本機 Prometheus 與 Grafana volume：

```bash
docker compose down -v
```

> `admin` / `admin` 僅供本機課程使用，不可沿用到共享或正式環境。

### 路徑二：執行 Python package 與 notebooks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[course]"
```

重新產生 synthetic data：

```bash
aiops-simulate --days 30 --out-dir data/synthetic
```

啟動 JupyterLab：

```bash
jupyter lab notebooks
```

Windows 與較完整的初學者設定說明見 [`hands-on/aiops-anomaly-detection/getting-started/README.md`](hands-on/aiops-anomaly-detection/getting-started/README.md)。

## Notebook 路徑

建議依序執行：

1. `data/synthetic/simulator_rrd_metrics.ipynb`
2. `notebooks/Notebook1_Time_Series_Features.ipynb`
3. `notebooks/Notebook2_Baseline_Anomaly_Detection.ipynb`
4. `notebooks/Notebook3_SPC_for_AD.ipynb`
5. `notebooks/Notebook4_ML_Unsupervised_for_AD.ipynb`
6. `notebooks/Notebook5_AD_Alert_Reduction.ipynb`
7. `notebooks/Notebook6_Forecasting.ipynb`
8. `notebooks/Notebook7_Root_Cause_Analysis_with_LLM.ipynb`

## 課程架構

| 路徑 | 學習成果 | 目前狀態 |
| --- | --- | --- |
| 可觀測性基礎 | 啟動 Prometheus/Grafana、讀懂 metrics、操作 dashboard | 第一個 lab 已建立 |
| Network AIOps | 特徵工程、統計與 ML 異常偵測、告警降噪、預測、RCA | package 與 7 個 notebooks 已建立 |
| 營運整合 | alerting、SLO、事件關聯、部署與治理 | 規劃中 |

完整模組、學習產出與完成標準見 [`curriculum/README.md`](curriculum/README.md)。

## Repository 結構

```text
.
├── src/aiops_monitor/           # 可測試、可安裝的 simulator/anomaly/exporter package
├── compose.yaml                 # Prometheus、Grafana 與 RRD exporter
├── prometheus/                  # scrape configuration
├── grafana/                     # datasource、dashboard provisioning
├── labs/                        # 可重複執行的操作實驗
├── curriculum/                  # 課程地圖與完成標準
├── course_materials/            # 網路介面監控概念文件
├── data/                        # synthetic、sample、processed data
├── notebooks/                   # AIOps 教學 notebooks
├── hands-on/                    # 初學者環境設定與短版練習
├── reports/                     # RCA 輸出範例
├── scripts/                     # notebook 建置與課程維護工具
└── tests/                       # package regression tests
```

## Python command surface

產生 RRD-like dataset：

```bash
aiops-simulate --days 30 --seed 42 --out-dir data/synthetic
```

在本機直接啟動 metrics exporter：

```bash
CSV_PATH=data/synthetic/synthetic_rrd_metrics.csv aiops-export
```

## 資料

```text
data/
├── synthetic/   # 可由 simulator 重建的 RRD-like metrics
├── sample/      # LibreNMS/RRDTool sample data
└── processed/   # notebooks 產出的 features、alerts、forecast 與 RCA 結果
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

本課程參考 [grafana-zero-to-hero](https://github.com/blueswen/grafana-zero-to-hero) 與 [observability-zero-to-hero](https://github.com/iam-veeramalla/observability-zero-to-hero) 的課程組織方式，但範例、資料、程式與練習均在本 repository 中獨立設計。比較結果與品質目標見 [`docs/reference-analysis.md`](docs/reference-analysis.md)。

## License

[MIT](LICENSE)
