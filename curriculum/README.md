# 課程地圖

本課程採用「先看見、再判斷、最後行動」的順序。每一模組都要產出可檢查的 artifact，而不只完成閱讀或觀看。

## 初學者核心路徑

| 模組 | 主題 | 學員產出 | 狀態 |
| --- | --- | --- | --- |
| 00 | 環境與可觀測性心智模型 | 可執行環境檢查結果 | 規劃中 |
| 01 | Prometheus 與 Grafana 本機環境 | 可查詢 metrics 與預設 dashboard | 已建立 |
| 02 | Network metrics 與 PromQL | 查詢表、單位說明、四個診斷 query | 規劃中 |
| 03 | Dashboard 設計 | 能區分流量、延遲、錯誤與遺失的 dashboard | 規劃中 |
| 04 | 時序特徵工程 | `features.csv` 與特徵解釋 | 已建立 |
| 05 | Baseline 與 SPC 異常偵測 | 可比較的 anomaly flags | 已建立 |
| 06 | 非監督式異常偵測 | anomaly scores 與閾值選擇紀錄 | 已建立 |
| 07 | 告警與降噪 | raw/reduced alerts 與分組規則 | 已建立 |
| 08 | 預測與容量規劃 | forecast、誤差與容量判讀 | 已建立 |
| 09 | 根因分析 | evidence table 與 RCA report | 已建立 |
| 10 | 事件處置 | runbook 與復原驗證 | 規劃中 |
| 11 | Capstone | 可重現 incident、dashboard、alerts、RCA 與改善提案 | 規劃中 |

## 進階路徑

核心路徑完成後，再加入以下內容：

- Alertmanager 與通知路由；
- SLI、SLO 與 error budget；
- logs、traces 與 OpenTelemetry correlation；
- Kubernetes monitoring；
- dashboard 與 alert rules as code；
- model monitoring、drift 與 evaluation；
- LLM-assisted RCA 的 evidence boundary、failure modes 與人工覆核。

## 每個 lab 的固定結構

每個 lab README 應依序回答：

1. 完成後能做什麼？
2. 會啟動哪些元件，資料如何流動？
3. 前置需求是否已滿足？
4. 要執行哪些指令？
5. 正確結果長什麼樣？
6. 如何故意製造或切換情境？
7. 常見失敗如何定位？
8. 要保留哪些產出？
9. 如何停止與清除環境？

## 完成標準

看見 dashboard 不等於完成 lab。學員必須能用 query 解釋圖形、指出資料來源、重現指定情境，並留下規定的 artifact。模型模組還必須記錄資料切分、評估指標與錯誤案例。
