# Error Log Sample

此資料夾收錄三竹提供的 LibreNMS / RRDTool 網路監控範例資料。它是選讀資料，不是 labs 的必要輸入。

主教材已經把同類型欄位整理成 `data/synthetic/synthetic_rrd_metrics.csv`，所以初學者可以先跳過本資料夾。

## 內容

- `read_rrd.ipynb`：讀取 RRD 檔的範例 Notebook，已改為專案相對路徑。
- `rrd_helper.py`：以系統 `rrdtool` command line 包裝 `info` 與 `fetch`。
- `資訊部/LibreNMS網路監控/Firewall_RRD_Log(Triggered off)/*.rrd`：5 個 firewall port 的 RRD sample files。

## 系統需求

除了 Python 套件外，讀取 `.rrd` 需要本機安裝 RRDtool：

```bash
brew install rrdtool
```

## 已驗證結果

使用 `rrdtool 1.9.0` 驗證 5 個 `.rrd` 檔皆可讀：

- `port-id7427.rrd`
- `port-id7428.rrd`
- `port-id7429.rrd`
- `port-id7430.rrd`
- `port-id7431.rrd`

每個檔案皆為 300 秒解析度，並包含 15 個 data sources：

```text
INOCTETS, OUTOCTETS,
INERRORS, OUTERRORS,
INUCASTPKTS, OUTUCASTPKTS,
INNUCASTPKTS, OUTNUCASTPKTS,
INDISCARDS, OUTDISCARDS,
INUNKNOWNPROTOS,
INBROADCASTPKTS, OUTBROADCASTPKTS,
INMULTICASTPKTS, OUTMULTICASTPKTS
```
