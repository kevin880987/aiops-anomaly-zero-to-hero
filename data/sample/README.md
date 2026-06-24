# Sample Data（選讀）

選讀資料，不是 labs 的必要輸入。Labs 使用 `data/synthetic/` 即可完成。只有在想理解 LibreNMS / RRDTool 原始 `.rrd` 檔格式時，才進入本目錄。

## mitake_error_log/

三竹資訊提供的 LibreNMS / RRDTool 網路監控範例資料。主教材已將同類型欄位整理成 `data/synthetic/synthetic_rrd_metrics.csv`。

**內容：**

- `read_rrd.ipynb`：讀取 RRD 檔的範例 Notebook。
- `rrd_helper.py`：以系統 `rrdtool` 指令包裝 `info` 與 `fetch`。
- `資訊部/LibreNMS網路監控/Firewall_RRD_Log(Triggered off)/*.rrd`：5 個 firewall port 的 RRD sample files。

**系統需求：** 讀取 `.rrd` 需要本機安裝 RRDtool：

```bash
brew install rrdtool
```

**已驗證：** 以 `rrdtool 1.9.0` 確認 5 個檔案（port-id7427–7431.rrd）皆可讀，300 秒解析度，各含 15 個 data sources：

```text
INOCTETS, OUTOCTETS, INERRORS, OUTERRORS,
INUCASTPKTS, OUTUCASTPKTS, INNUCASTPKTS, OUTNUCASTPKTS,
INDISCARDS, OUTDISCARDS, INUNKNOWNPROTOS,
INBROADCASTPKTS, OUTBROADCASTPKTS, INMULTICASTPKTS, OUTMULTICASTPKTS
```
