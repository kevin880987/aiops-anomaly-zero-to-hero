# AIOps Anomaly Detection: Zero to Hero

從網路 telemetry 到 AIOps 決策支援的完整實作課程。學員在本機執行 Prometheus 與 exporter，選擇Grafana local 或 Grafana Cloud 作為視覺化層，完成特徵工程、異常偵測、告警降噪、預測與根因分析。

Grafana Cloud path 需要免費帳號（免安裝，瀏覽器即可使用）；Grafana local path 不需要帳號。課程著重演算法層面：特徵工程、偵測方法選擇、告警設計與根因判讀。

---

## 開始使用

**需要設定環境：** → [`labs/getting-started/`](labs/getting-started/README.md) — 環境設定步驟、路徑選擇、就緒確認，全部在這裡。

**已有自己的環境：** → [`labs/getting-started/05-readiness-check.md`](labs/getting-started/05-readiness-check.md) — 直接確認 Python 套件、Prometheus、Grafana 是否符合課程需求。

---

## Repository 結構

```text
.
├── README.md                    # 本文件：repo 介紹與導覽
├── COURSE_GUIDE.md              # 教材總覽、學習成果、路線與評量方式
├── environment.yml              # conda 課程環境
├── labs/
│   ├── getting-started/         # 設定指南（01a–01c、02–04）與就緒確認（05）
│   ├── workshop/                # 工作坊短版 notebooks
│   └── self-study/              # 完整自學版 notebooks
├── data/
│   ├── synthetic/               # 可由 simulator 重建的 RRD-like metrics
│   └── sample/                  # LibreNMS/RRDTool sample data
├── outputs/                     # Labs 產出（gitignored）
│   ├── workshop/
│   └── self-study/
└── infra/
    ├── prometheus/              # Prometheus 設定（prometheus.yml / prometheus.windows.yml）
    ├── grafana/                 # Dashboard JSON 與 datasource 設定
    └── exporter.py              # CSV-to-Prometheus metrics exporter
```

---

## 課程設計原則

- 每個 lab 都有明確輸入、操作、驗證方法、預期結果與清除步驟。
- 故障情境必須可重現，不能只展示完成後的 dashboard。
- Dashboard、告警與模型輸出必須能追溯到原始 telemetry。
- 生成式 AI 只能協助解釋有證據的訊號，不替代監控資料或驗證程序。

範例、資料、程式與練習均在本 repository 中獨立設計。

## License

[MIT](LICENSE)
