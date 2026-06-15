# 網路介面監控 RCA 根本原因分析流程

## 1. RCA 的目的

在網路介面監控中，RCA 的目標不是只找出「哪個欄位異常」，而是要回答：

```text
這個異常比較像哪一類問題？
可能根因是什麼？
應該往哪裡排查？
可以採取什麼處置？
```

可以用一條簡單 pipeline 表示：

```text
Metrics 異常
→ 多欄位交互作用
→ 問題型態分類
→ Root Cause Candidate Ranking
→ Runbook / Action
```

---

## 2. RCA 基本流程

建議流程：

```text
Step 1. 建立正常 baseline
Step 2. 偵測異常欄位
Step 3. 找出同一時間窗內共同異常的欄位
Step 4. 用規則或模型判斷問題型態
Step 5. 輸出 root cause candidate 與處理建議
```

若資料每 300 秒一筆，可以以 5–15 分鐘為短時間窗，以 1 小時、1 天或 7 天同時段建立 baseline。

---

## 3. 異常偵測方法

### 方法一：固定門檻

例如：

```text
ifInOctets_rate > 100 Mbps
ifOutOctets_rate > 50 Mbps
```

優點是簡單，適合早期監控。

缺點是不適合處理日夜週期與不同 port 的正常負載差異。

---

### 方法二：Rolling Statistics

```text
current value > rolling mean + 3 × rolling std
```

適合簡單教學，但網路流量常不符合常態分布，因此要小心尖峰與長尾。

---

### 方法三：Robust Baseline

建議使用：

```text
robust_z = (x - rolling median) / MAD
```

或：

```text
current value > historical 95th percentile of same time-of-day
```

比較適合流量資料，因為對尖峰與偏態較穩健。

---

## 4. RCA Evidence Rules

可先用規則建立可解釋的 RCA prototype。

| Evidence Rule | Root Cause Candidate |
|---|---|
| `OCTETS ↑` + `UCASTPKTS ↑` + `DISCARDS ≈ 0` | 正常業務流量增加 |
| `UCASTPKTS ↑↑` + `OCTETS 小幅↑` | 大量小封包 / 掃描 / 短連線暴增 |
| `OCTETS ↑↑` + `UCASTPKTS 中度↑` | 大檔案傳輸 / 備份 / 串流 |
| `OCTETS ↑↑` + `DISCARDS ↑` + `ERRORS ≈ 0` | 頻寬壅塞 / Queue 滿 |
| `DISCARDS ↑` + `ERRORS ≈ 0` | Bufferbloat / QoS / queue 問題 |
| `ERRORS ↑` + `DISCARDS 不一定↑` | 線路品質 / port / SFP / NIC 問題 |
| `OCTETS ↑` 後 `ERRORS ↑` | 高負載下線路不穩 |
| `BROADCAST ↑↑` + `NUCAST ↑↑` + 多 port 同時↑ | Broadcast storm / L2 loop |
| `MULTICAST ↑↑` + 多 port 同時↑ | Multicast flooding / IGMP 問題 |
| 多個 `OUT*PKTS ↑` + `OUTOCTETS ↑` | 異常設備大量發送 |
| `INUNKNOWNPROTOS ↑` + `INPKTS ↑` | 協定異常 / 掃描 / 設定錯誤 |

---

## 5. Root Cause Scoring

可用簡單 scoring 方式排序根因候選。

例如對「Queue congestion」：

| Evidence | 權重 |
|---|---:|
| `DISCARDS ↑` | 3 |
| `ERRORS ≈ 0` | 2 |
| `OCTETS ↑↑` | 2 |
| `UCASTPKTS ↑` | 1 |

若同一時間窗符合多個 evidence，則加總分數：

```text
score(root cause) = Σ evidence_weight
```

輸出分數最高的 root cause candidates。

---

## 6. RCA 輸出格式範例

```text
Detected issue:
Queue congestion / buffer pressure

Evidence:
- OUTOCTETS 在 18:00–18:20 高於 rolling 95th percentile
- OUTDISCARDS 同時上升
- OUTERRORS 維持 0
- UCASTPKTS 同步上升

Root cause candidate:
- 高流量造成 queue / buffer 壓力
- 可能是備份、同步、下載或 QoS 設定導致

Recommended action:
- 檢查該時間窗 top talker
- 檢查 QoS / queue 設定
- 檢查是否有排程備份或大量同步
- 若長期發生，評估擴充頻寬
```

---

## 7. Knowledge Graph 概念

可將 RCA 表示成 knowledge graph：

```text
Metric Node
→ Pattern Node
→ Alert Event
→ Evidence Rule
→ Root Cause Candidate
→ Context Node
→ Runbook / Action
```

### 主要節點

| 節點類型 | 範例 |
|---|---|
| Metrics | OCTETS, UCASTPKTS, ERRORS, DISCARDS, BROADCAST, MULTICAST, UNKNOWNPROTOS |
| Time-series Pattern | spike, plateau, periodic, gradual increase, sparse non-zero |
| Evidence Rules | OCTETS high + DISCARDS high + ERRORS low |
| Root Cause Candidates | queue congestion, link quality issue, broadcast storm |
| Context | port, device, time window, logs, top talker, port status |
| Actions | check QoS, replace cable, inspect STP, check IGMP |

---

## 8. RCA 與 Logs 的整合

RRD / Metrics 是 Layer 1。若要做更完整 RCA，可以接 Layer 2 Logs。

例如：

```text
Metrics:
BROADCAST ↑↑ + 多 port 同時 ↑

Logs:
STP topology change detected
MAC flapping on port Gi1/0/24

RCA:
High confidence: L2 loop or unstable switch link
```

常見可結合的 logs：

- Interface up/down
- STP topology change
- MAC flapping
- DHCP abnormal messages
- IGMP events
- Routing protocol changes
- Device reboot
- Port security violation

---

## 9. 教學版 RCA Notebook 建議

Notebook 可以包含：

1. 讀取 RRD 轉出的 CSV。
2. 做 time window 與 rolling features。
3. 建立 baseline。
4. 產生 anomaly flags。
5. 套用 evidence rules。
6. 計算 root cause candidate score。
7. 輸出 RCA 摘要。
8. 畫出 evidence plot。

### 範例輸出

```text
[18:10–18:25] Possible queue congestion

Evidence:
- OUTOCTETS high
- OUTDISCARDS high
- OUTERRORS normal

Confidence: 0.82

Suggested action:
Check top talker / QoS / backup jobs
```

---

## 10. RCA 教學重點

```text
單一欄位：看哪裡異常
多欄位交互：看異常型態
時間窗關聯：看是否同時發生
Context / Logs：提高根因信心
Runbook：轉成可行動處置
```
