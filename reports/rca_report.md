# RCA Report

本報告由 Notebook7 根據 reduced alerts 與 metric interaction rules 產生，可作為 LLM prompt 或人工診斷摘要。

## RCA-023 - Business traffic growth or large transfer

- 事件時間：2026-02-01 01:50:00 - 2026-02-01 01:55:00
- 影響介面：port-id7427,port-id7429,port-id7431
- 問題型態：Traffic surge / capacity pressure
- 主要證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 01:50:00 - 2026-02-01 01:55:00
影響介面：port-id7427,port-id7429,port-id7431
問題類型：Traffic surge / capacity pressure
RCA 候選：Business traffic growth or large transfer
證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
嚴重度：100
信心：High
```

## RCA-040 - Business traffic growth or large transfer

- 事件時間：2026-02-01 02:45:00 - 2026-02-01 02:55:00
- 影響介面：port-id7427,port-id7429,port-id7430,port-id7431
- 問題型態：Traffic surge / capacity pressure
- 主要證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 02:45:00 - 2026-02-01 02:55:00
影響介面：port-id7427,port-id7429,port-id7430,port-id7431
問題類型：Traffic surge / capacity pressure
RCA 候選：Business traffic growth or large transfer
證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
嚴重度：100
信心：High
```

## RCA-045 - Multicast flooding

- 事件時間：2026-02-01 03:00:00 - 2026-02-01 03:10:00
- 影響介面：port-id7429,port-id7431
- 問題型態：Multicast flooding
- 主要證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:00:00 - 2026-02-01 03:10:00
影響介面：port-id7429,port-id7431
問題類型：Multicast flooding
RCA 候選：Multicast flooding
證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
嚴重度：86
信心：High
```

## RCA-046 - Small packet scan or connection surge

- 事件時間：2026-02-01 03:00:00 - 2026-02-01 03:10:00
- 影響介面：port-id7429,port-id7431
- 問題型態：Packet surge / possible scan
- 主要證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:00:00 - 2026-02-01 03:10:00
影響介面：port-id7429,port-id7431
問題類型：Packet surge / possible scan
RCA 候選：Small packet scan or connection surge
證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
嚴重度：86
信心：High
```

## RCA-047 - Business traffic growth or large transfer

- 事件時間：2026-02-01 03:05:00 - 2026-02-01 03:10:00
- 影響介面：port-id7428,port-id7430,port-id7431
- 問題型態：Traffic surge / capacity pressure
- 主要證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:05:00 - 2026-02-01 03:10:00
影響介面：port-id7428,port-id7430,port-id7431
問題類型：Traffic surge / capacity pressure
RCA 候選：Business traffic growth or large transfer
證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
嚴重度：100
信心：High
```

## RCA-049 - Broadcast storm / L2 loop

- 事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
- 影響介面：port-id7427,port-id7430,port-id7431
- 問題型態：Broadcast storm / L2 loop
- 主要證據：BROADCAST high across ports | NUCAST high may rise together | Check STP, loop, ARP storm, DHCP storm, VLAN scope
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
影響介面：port-id7427,port-id7430,port-id7431
問題類型：Broadcast storm / L2 loop
RCA 候選：Broadcast storm / L2 loop
證據：BROADCAST high across ports | NUCAST high may rise together | Check STP, loop, ARP storm, DHCP storm, VLAN scope
嚴重度：100
信心：High
```

## RCA-050 - Multicast flooding

- 事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
- 影響介面：port-id7427,port-id7430,port-id7431
- 問題型態：Multicast flooding
- 主要證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
影響介面：port-id7427,port-id7430,port-id7431
問題類型：Multicast flooding
RCA 候選：Multicast flooding
證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
嚴重度：100
信心：High
```

## RCA-051 - Small packet scan or connection surge

- 事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
- 影響介面：port-id7427,port-id7430,port-id7431
- 問題型態：Packet surge / possible scan
- 主要證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:15:00 - 2026-02-01 03:25:00
影響介面：port-id7427,port-id7430,port-id7431
問題類型：Packet surge / possible scan
RCA 候選：Small packet scan or connection surge
證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
嚴重度：100
信心：High
```

## RCA-054 - Broadcast storm / L2 loop

- 事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
- 影響介面：port-id7428,port-id7430,port-id7431
- 問題型態：Broadcast storm / L2 loop
- 主要證據：BROADCAST high across ports | NUCAST high may rise together | Check STP, loop, ARP storm, DHCP storm, VLAN scope
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
影響介面：port-id7428,port-id7430,port-id7431
問題類型：Broadcast storm / L2 loop
RCA 候選：Broadcast storm / L2 loop
證據：BROADCAST high across ports | NUCAST high may rise together | Check STP, loop, ARP storm, DHCP storm, VLAN scope
嚴重度：100
信心：High
```

## RCA-055 - Multicast flooding

- 事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
- 影響介面：port-id7428,port-id7430,port-id7431
- 問題型態：Multicast flooding
- 主要證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
影響介面：port-id7428,port-id7430,port-id7431
問題類型：Multicast flooding
RCA 候選：Multicast flooding
證據：MULTICAST high across ports | DISCARDS may rise | Check IGMP snooping, querier, IPTV or routing protocol behavior
嚴重度：100
信心：High
```

## RCA-056 - Small packet scan or connection surge

- 事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
- 影響介面：port-id7428,port-id7429,port-id7430,port-id7431
- 問題型態：Packet surge / possible scan
- 主要證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
影響介面：port-id7428,port-id7429,port-id7430,port-id7431
問題類型：Packet surge / possible scan
RCA 候選：Small packet scan or connection surge
證據：UCASTPKTS high | OCTETS may be flat or only mildly high | Check port scan, short connections, DDoS small packets, heartbeat surge
嚴重度：100
信心：High
```

## RCA-057 - Business traffic growth or large transfer

- 事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
- 影響介面：port-id7428,port-id7429,port-id7430,port-id7431
- 問題型態：Traffic surge / capacity pressure
- 主要證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
- 根因分數：100
- 信心分數：High

### LLM Prompt

```text
你是一位 AIOps / Network RCA 助理。
請根據以下監控證據判斷可能根因，並輸出：
1. 問題型態
2. 主要證據
3. 可能根因
4. 建議處置
5. 信心分數

事件時間：2026-02-01 03:30:00 - 2026-02-01 03:40:00
影響介面：port-id7428,port-id7429,port-id7430,port-id7431
問題類型：Traffic surge / capacity pressure
RCA 候選：Business traffic growth or large transfer
證據：OCTETS high | Compare packet growth and avg_packet_size | Check backup, data sync, download, upload, streaming, or capacity pressure
嚴重度：100
信心：High
```
