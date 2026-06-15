import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": textwrap.dedent(source).strip().splitlines(True),
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": textwrap.dedent(source).strip().splitlines(True),
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(path: Path, cells: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=2), encoding="utf-8")


SETUP = """
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

plt.style.use("seaborn-v0_8-whitegrid")
pd.set_option("display.max_columns", 120)
pd.set_option("display.width", 160)

def show_fig(fig):
    display(fig)
    plt.close(fig)

PROJECT_ROOT = Path.cwd()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent
elif not (PROJECT_ROOT / "data").exists():
    PROJECT_ROOT = Path("..").resolve()

DATA_SYNTHETIC = PROJECT_ROOT / "data" / "synthetic"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
REPORTS = PROJECT_ROOT / "reports"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

print(f"Project root: {PROJECT_ROOT}")
"""


def event_band_code(ax_name: str = "ax") -> str:
    return f"""
for _, event in event_catalog.iterrows():
    start = pd.to_datetime(event["start_time"])
    end = pd.to_datetime(event["end_time"])
    {ax_name}.axvspan(start, end, alpha=0.10, color="tab:red")
    {ax_name}.text(start, {ax_name}.get_ylim()[1], event["event_id"], fontsize=8, va="top", color="tab:red")
"""


def notebook1() -> list[dict]:
    return [
        md(
            """
            # Notebook1 - Time Series Features

            ## 學習目標

            本 notebook 將 raw RRD-like metrics 轉換成可用於異常偵測的時間序列特徵。

            對應教學設計：
            - timestamp index 與欄位型態整理
            - resampling / missing value 檢查
            - rolling statistics
            - lag features
            - rate / ratio features
            - inbound vs outbound comparison
            """
        ),
        md(
            """
            ## Step 0 - 環境與輸入資料

            輸入：`data/synthetic/synthetic_rrd_metrics.csv`

            輸出：`data/processed/features.csv`
            """
        ),
        code(SETUP),
        code(
            """
            raw_path = DATA_SYNTHETIC / "synthetic_rrd_metrics.csv"
            event_path = DATA_SYNTHETIC / "synthetic_event_catalog.csv"

            df = pd.read_csv(raw_path, parse_dates=["timestamp"])
            event_catalog = pd.read_csv(event_path, parse_dates=["start_time", "end_time"])
            df = df.sort_values(["device_id", "port_id", "timestamp"]).reset_index(drop=True)

            print(f"rows: {len(df):,}")
            print(f"ports: {df['port_id'].nunique()}")
            print(f"time range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
            display(df.head())
            display(event_catalog)
            """
        ),
        md("## Step 1 - 資料品質檢查\n\n確認每個 port 的時間解析度、缺值比例與事件標籤分布。"),
        code(
            """
            metric_cols = [
                "INOCTETS", "OUTOCTETS", "INERRORS", "OUTERRORS",
                "INUCASTPKTS", "OUTUCASTPKTS", "INNUCASTPKTS", "OUTNUCASTPKTS",
                "INDISCARDS", "OUTDISCARDS", "INUNKNOWNPROTOS",
                "INBROADCASTPKTS", "OUTBROADCASTPKTS", "INMULTICASTPKTS", "OUTMULTICASTPKTS",
            ]

            quality = (
                df.groupby(["device_id", "port_id"])
                .agg(
                    rows=("timestamp", "size"),
                    start=("timestamp", "min"),
                    end=("timestamp", "max"),
                    event_rows=("event_id", lambda s: (s.astype(str) != "").sum()),
                )
                .reset_index()
            )
            missing = df[metric_cols].isna().mean().rename("missing_rate").reset_index().rename(columns={"index": "metric"})
            display(quality)
            display(missing)
            """
        ),
        md("## Step 2 - 建立監控語意特徵\n\n將原始欄位轉成總量、比例與 rate。這些特徵會在後續 notebook 中重複使用。"),
        code(
            """
            def safe_divide(a, b):
                return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=np.asarray(b) != 0)


            df["traffic_total"] = df["INOCTETS"] + df["OUTOCTETS"]
            df["ucast_total"] = df["INUCASTPKTS"] + df["OUTUCASTPKTS"]
            df["nucast_total"] = df["INNUCASTPKTS"] + df["OUTNUCASTPKTS"]
            df["errors_total"] = df["INERRORS"] + df["OUTERRORS"]
            df["discards_total"] = df["INDISCARDS"] + df["OUTDISCARDS"]
            df["broadcast_total"] = df["INBROADCASTPKTS"] + df["OUTBROADCASTPKTS"]
            df["multicast_total"] = df["INMULTICASTPKTS"] + df["OUTMULTICASTPKTS"]
            df["unknown_total"] = df["INUNKNOWNPROTOS"]

            df["avg_packet_size"] = safe_divide(df["traffic_total"].to_numpy(), df["ucast_total"].to_numpy())
            df["error_rate"] = safe_divide(df["errors_total"].to_numpy(), df["ucast_total"].to_numpy())
            df["discard_rate"] = safe_divide(df["discards_total"].to_numpy(), df["ucast_total"].to_numpy())
            df["broadcast_ratio"] = safe_divide(df["broadcast_total"].to_numpy(), df["ucast_total"].to_numpy())
            df["multicast_ratio"] = safe_divide(df["multicast_total"].to_numpy(), df["ucast_total"].to_numpy())
            df["in_out_octets_ratio"] = safe_divide(df["INOCTETS"].to_numpy(), df["OUTOCTETS"].to_numpy())

            feature_preview = [
                "timestamp", "device_id", "port_id", "event_label",
                "traffic_total", "ucast_total", "avg_packet_size",
                "error_rate", "discard_rate", "broadcast_ratio", "multicast_ratio",
            ]
            display(df[feature_preview].head())
            display(df[["traffic_total", "ucast_total", "avg_packet_size", "error_rate", "discard_rate"]].describe())
            """
        ),
        md("## Step 3 - 視覺化：流量、封包與錯誤/丟棄\n\n這對應 Grafana 的流量 trend、封包 trend、error / discard rate panels。"),
        code(
            """
            sample_port = "port-id7427"
            plot_df = df[df["port_id"] == sample_port].copy()

            fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
            axes[0].plot(plot_df["timestamp"], plot_df["INOCTETS"], label="INOCTETS", linewidth=1)
            axes[0].plot(plot_df["timestamp"], plot_df["OUTOCTETS"], label="OUTOCTETS", linewidth=1)
            axes[0].set_title(f"{sample_port} - In / Out Octets")
            axes[0].legend(loc="upper left")

            axes[1].plot(plot_df["timestamp"], plot_df["ucast_total"], color="tab:green", label="ucast_total", linewidth=1)
            axes[1].set_title("Unicast Packets")
            axes[1].legend(loc="upper left")

            axes[2].plot(plot_df["timestamp"], plot_df["error_rate"], label="error_rate", linewidth=1)
            axes[2].plot(plot_df["timestamp"], plot_df["discard_rate"], label="discard_rate", linewidth=1)
            axes[2].set_title("Error / Discard Rate")
            axes[2].legend(loc="upper left")

            for ax in axes:
                for _, event in event_catalog.iterrows():
                    if event["port_id"] in [sample_port, "MULTI"]:
                        ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
                ax.grid(alpha=0.25)

            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 4 - Rolling statistics 與 lag features\n\n建立 1 小時 rolling 與 1 天 p95 / MAD，支援 baseline、SPC 與 ML。"),
        code(
            """
            def rolling_mad(series):
                median = np.median(series)
                return np.median(np.abs(series - median))


            base_features = [
                "traffic_total", "ucast_total", "errors_total", "discards_total",
                "broadcast_total", "multicast_total", "unknown_total",
                "avg_packet_size", "error_rate", "discard_rate", "broadcast_ratio", "multicast_ratio",
            ]

            feature_frames = []
            for (_, port_id), g0 in df.groupby(["device_id", "port_id"], sort=False):
                g = g0.sort_values("timestamp").set_index("timestamp").copy()
                generated = {}
                for col in base_features:
                    generated[f"{col}_rolling_mean_1h"] = g[col].rolling("60min", min_periods=3).mean()
                    generated[f"{col}_rolling_std_1h"] = g[col].rolling("60min", min_periods=3).std()
                    generated[f"{col}_rolling_median_1h"] = g[col].rolling("60min", min_periods=3).median()
                    generated[f"{col}_rolling_p95_1d"] = g[col].rolling("1d", min_periods=12).quantile(0.95)
                    generated[f"{col}_rolling_mad_1d"] = g[col].rolling("1d", min_periods=12).apply(rolling_mad, raw=True)
                    generated[f"{col}_lag_5m"] = g[col].shift(1)
                    generated[f"{col}_lag_1h"] = g[col].shift(12)
                g = pd.concat([g, pd.DataFrame(generated, index=g.index)], axis=1)
                feature_frames.append(g.reset_index())

            features = pd.concat(feature_frames, ignore_index=True).bfill().fillna(0)
            print(f"feature columns: {len(features.columns)}")
            display(features[["timestamp", "port_id", "traffic_total", "traffic_total_rolling_mean_1h", "traffic_total_rolling_p95_1d"]].head())
            """
        ),
        md("## Step 5 - 視覺化：rolling baseline 與 avg packet size\n\n觀察大量小封包與大檔案傳輸時，`avg_packet_size` 如何改變。"),
        code(
            """
            fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
            p = features[features["port_id"] == "port-id7428"].copy()
            axes[0].plot(p["timestamp"], p["traffic_total"], label="traffic_total", linewidth=1)
            axes[0].plot(p["timestamp"], p["traffic_total_rolling_mean_1h"], label="rolling_mean_1h", linewidth=1.4)
            axes[0].plot(p["timestamp"], p["traffic_total_rolling_p95_1d"], label="rolling_p95_1d", linewidth=1.2)
            axes[0].set_title("Traffic vs rolling baselines")
            axes[0].legend(loc="upper left")

            axes[1].plot(p["timestamp"], p["avg_packet_size"], label="avg_packet_size", color="tab:purple", linewidth=1)
            axes[1].plot(p["timestamp"], p["avg_packet_size_rolling_median_1h"], label="rolling_median_1h", color="tab:orange", linewidth=1.2)
            axes[1].set_title("Average packet size")
            axes[1].legend(loc="upper left")

            for ax in axes:
                for _, event in event_catalog.iterrows():
                    if event["port_id"] in ["port-id7428", "MULTI"]:
                        ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
                ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 6 - 輸出 features.csv"),
        code(
            """
            out_path = DATA_PROCESSED / "features.csv"
            features.to_csv(out_path, index=False)
            print(f"saved: {out_path}")
            """
        ),
        md(
            """
            ## 小結

            本 notebook 完成 Metrics → Features 的轉換。下一步會用這些 rolling baseline、ratio 與 rate 建立 rule-based anomaly flags。
            """
        ),
    ]


def notebook2() -> list[dict]:
    return [
        md("# Notebook2 - Baseline Anomaly Detection\n\n用 rolling mean/std、rolling median/MAD 與 percentile threshold 建立可解釋的 baseline anomaly detection。"),
        md("## Step 0 - 讀取 Notebook1 輸出的 features"),
        code(SETUP),
        code(
            """
            features = pd.read_csv(DATA_PROCESSED / "features.csv", parse_dates=["timestamp"])
            event_catalog = pd.read_csv(DATA_SYNTHETIC / "synthetic_event_catalog.csv", parse_dates=["start_time", "end_time"])
            print(features.shape)
            display(features[["timestamp", "port_id", "event_label", "traffic_total", "ucast_total", "errors_total", "discards_total"]].head())
            """
        ),
        md("## Step 1 - 定義 baseline 方法與 anomaly flags\n\n每個監控維度同時計算 z-score、robust z-score 與 p95 exceed。"),
        code(
            """
            flag_map = {
                "traffic_high": "traffic_total",
                "packets_high": "ucast_total",
                "errors_high": "errors_total",
                "discards_high": "discards_total",
                "broadcast_high": "broadcast_total",
                "multicast_high": "multicast_total",
                "unknown_high": "unknown_total",
            }

            result = features[["timestamp", "device_id", "port_id", "port_role", "event_label", "event_id"] + list(flag_map.values())].copy()
            for flag, col in flag_map.items():
                mean = features[f"{col}_rolling_mean_1h"]
                std = features[f"{col}_rolling_std_1h"].replace(0, np.nan)
                median = features[f"{col}_rolling_median_1h"]
                mad = features[f"{col}_rolling_mad_1d"].replace(0, np.nan)
                p95 = features[f"{col}_rolling_p95_1d"]

                result[f"{col}_z_score"] = ((features[col] - mean) / std).replace([np.inf, -np.inf], 0).fillna(0)
                result[f"{col}_robust_z"] = (0.6745 * (features[col] - median) / mad).replace([np.inf, -np.inf], 0).fillna(0)
                result[f"{col}_percentile_exceed"] = features[col] > p95
                result[flag] = (
                    (result[f"{col}_z_score"] > 3.0)
                    | (result[f"{col}_robust_z"] > 4.0)
                    | (result[f"{col}_percentile_exceed"] & (features[col] > 0))
                )

            flag_cols = list(flag_map.keys())
            result["baseline_alert_count"] = result[flag_cols].sum(axis=1)
            result["any_baseline_anomaly"] = result["baseline_alert_count"] > 0
            display(result.loc[result["any_baseline_anomaly"], ["timestamp", "port_id", "event_label", "baseline_alert_count"] + flag_cols].head(12))
            """
        ),
        md("## Step 2 - 視覺化：原始值 + baseline band + anomaly markers"),
        code(
            """
            port_id = "port-id7427"
            col = "traffic_total"
            p = features[features["port_id"] == port_id].copy()
            r = result[result["port_id"] == port_id].copy()

            fig, ax = plt.subplots(figsize=(14, 5))
            ax.plot(p["timestamp"], p[col], label=col, linewidth=1)
            ax.plot(p["timestamp"], p[f"{col}_rolling_mean_1h"], label="rolling_mean_1h", linewidth=1.2)
            upper = p[f"{col}_rolling_mean_1h"] + 3 * p[f"{col}_rolling_std_1h"]
            lower = (p[f"{col}_rolling_mean_1h"] - 3 * p[f"{col}_rolling_std_1h"]).clip(lower=0)
            ax.fill_between(p["timestamp"], lower, upper, alpha=0.18, label="mean ± 3std")
            anomalies = r[r["traffic_high"]]
            ax.scatter(anomalies["timestamp"], anomalies[col], color="tab:red", s=18, label="traffic_high")
            for _, event in event_catalog.iterrows():
                if event["port_id"] in [port_id, "MULTI"]:
                    ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
            ax.set_title(f"{port_id} - Baseline anomaly detection")
            ax.legend(loc="upper left")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 3 - 視覺化：不同 flags 的時間分布\n\n這對應 Grafana 的 anomaly flag time series 和 annotation。"),
        code(
            """
            daily_flags = result.set_index("timestamp")[flag_cols].resample("6h").sum()
            fig, ax = plt.subplots(figsize=(14, 5))
            daily_flags.plot(ax=ax, linewidth=1.4)
            ax.set_title("Baseline anomaly flags aggregated every 6 hours")
            ax.set_ylabel("flag count")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)

            event_recall = (
                result.groupby("event_label")
                .agg(rows=("timestamp", "size"), anomaly_rows=("any_baseline_anomaly", "sum"), avg_flags=("baseline_alert_count", "mean"))
                .assign(anomaly_rate=lambda x: x["anomaly_rows"] / x["rows"])
                .sort_values("anomaly_rate", ascending=False)
            )
            display(event_recall)
            """
        ),
        md("## Step 4 - 輸出 baseline_anomaly_flags.csv"),
        code(
            """
            out_path = DATA_PROCESSED / "baseline_anomaly_flags.csv"
            result.to_csv(out_path, index=False)
            print(f"saved: {out_path}")
            """
        ),
    ]


def notebook3() -> list[dict]:
    return [
        md("# Notebook3 - SPC for AD\n\n將 Shewhart、EWMA、CUSUM 套用在網路監控特徵上，觀察不同異常型態的敏感度。"),
        code(SETUP),
        code(
            """
            features = pd.read_csv(DATA_PROCESSED / "features.csv", parse_dates=["timestamp"])
            event_catalog = pd.read_csv(DATA_SYNTHETIC / "synthetic_event_catalog.csv", parse_dates=["start_time", "end_time"])
            display(features[["timestamp", "port_id", "traffic_total", "discard_rate", "error_rate", "event_label"]].head())
            """
        ),
        md("## Step 1 - 以正常期間估計 control limits"),
        code(
            """
            rows = []
            for port_id, g in features.groupby("port_id", sort=False):
                g = g.sort_values("timestamp").copy()
                base = g[g["event_label"] == "normal"].head(7 * 24 * 12)
                traffic_mu = base["traffic_total"].mean()
                traffic_sigma = base["traffic_total"].std()
                discard_mu = base["discard_rate"].mean()
                discard_sigma = base["discard_rate"].std()
                error_mu = base["error_rate"].mean()
                error_sigma = base["error_rate"].std()

                g["traffic_center"] = traffic_mu
                g["traffic_ucl"] = traffic_mu + 3 * traffic_sigma
                g["traffic_lcl"] = max(0, traffic_mu - 3 * traffic_sigma)
                g["shewhart_traffic_violation"] = g["traffic_total"] > g["traffic_ucl"]

                lam = 0.25
                g["ewma_discard_rate"] = g["discard_rate"].ewm(alpha=lam, adjust=False).mean()
                g["ewma_discard_ucl"] = discard_mu + 3 * discard_sigma * np.sqrt(lam / (2 - lam))
                g["ewma_discard_violation"] = g["ewma_discard_rate"] > g["ewma_discard_ucl"]

                k = 0.5 * max(error_sigma, 1e-12)
                h = 5 * max(error_sigma, 1e-12)
                s = 0.0
                pos = []
                for value in g["error_rate"].fillna(0):
                    s = max(0, s + value - error_mu - k)
                    pos.append(s)
                g["cusum_error_pos"] = pos
                g["cusum_error_h"] = h
                g["cusum_error_violation"] = g["cusum_error_pos"] > h
                rows.append(g)

            spc = pd.concat(rows, ignore_index=True)
            spc["any_spc_violation"] = spc[["shewhart_traffic_violation", "ewma_discard_violation", "cusum_error_violation"]].any(axis=1)
            display(spc.loc[spc["any_spc_violation"], ["timestamp", "port_id", "event_label", "shewhart_traffic_violation", "ewma_discard_violation", "cusum_error_violation"]].head(12))
            """
        ),
        md("## Step 2 - 視覺化：Shewhart control chart"),
        code(
            """
            port_id = "port-id7427"
            p = spc[spc["port_id"] == port_id].copy()
            fig, ax = plt.subplots(figsize=(14, 5))
            ax.plot(p["timestamp"], p["traffic_total"], label="traffic_total", linewidth=1)
            ax.plot(p["timestamp"], p["traffic_center"], label="center", linewidth=1.1)
            ax.plot(p["timestamp"], p["traffic_ucl"], label="UCL", color="tab:red", linewidth=1.1)
            ax.plot(p["timestamp"], p["traffic_lcl"], label="LCL", color="tab:green", linewidth=1.1)
            v = p[p["shewhart_traffic_violation"]]
            ax.scatter(v["timestamp"], v["traffic_total"], color="tab:red", s=18, label="violation")
            for _, event in event_catalog.iterrows():
                if event["port_id"] in [port_id, "MULTI"]:
                    ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
            ax.set_title(f"{port_id} - Shewhart chart for traffic_total")
            ax.legend(loc="upper left")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 3 - 視覺化：EWMA 與 CUSUM\n\nEWMA 適合小幅持續偏移，CUSUM 適合累積性變化。"),
        code(
            """
            fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
            axes[0].plot(p["timestamp"], p["discard_rate"], alpha=0.35, label="discard_rate")
            axes[0].plot(p["timestamp"], p["ewma_discard_rate"], label="EWMA discard_rate")
            axes[0].plot(p["timestamp"], p["ewma_discard_ucl"], label="EWMA UCL", color="tab:red")
            axes[0].set_title("EWMA chart for discard_rate")
            axes[0].legend(loc="upper left")

            axes[1].plot(p["timestamp"], p["cusum_error_pos"], label="CUSUM error positive")
            axes[1].plot(p["timestamp"], p["cusum_error_h"], label="decision interval h", color="tab:red")
            axes[1].set_title("CUSUM chart for error_rate")
            axes[1].legend(loc="upper left")

            for ax in axes:
                for _, event in event_catalog.iterrows():
                    if event["port_id"] in [port_id, "MULTI"]:
                        ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
                ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 4 - SPC violation summary 與輸出"),
        code(
            """
            summary = (
                spc.groupby("event_label")
                .agg(rows=("timestamp", "size"), spc_violations=("any_spc_violation", "sum"))
                .assign(violation_rate=lambda x: x["spc_violations"] / x["rows"])
                .sort_values("violation_rate", ascending=False)
            )
            display(summary)

            keep = [
                "timestamp", "device_id", "port_id", "port_role", "event_label", "event_id",
                "traffic_total", "traffic_center", "traffic_ucl", "traffic_lcl", "shewhart_traffic_violation",
                "discard_rate", "ewma_discard_rate", "ewma_discard_ucl", "ewma_discard_violation",
                "error_rate", "cusum_error_pos", "cusum_error_h", "cusum_error_violation", "any_spc_violation",
            ]
            out_path = DATA_PROCESSED / "spc_results.csv"
            spc[keep].to_csv(out_path, index=False)
            print(f"saved: {out_path}")
            """
        ),
    ]


def notebook4() -> list[dict]:
    return [
        md("# Notebook4 - ML Unsupervised for AD\n\n使用 sliding-window features 與 Isolation Forest 進行多變量異常偵測，並用視覺化比較事件敏感度。"),
        code(SETUP),
        code(
            """
            features = pd.read_csv(DATA_PROCESSED / "features.csv", parse_dates=["timestamp"])
            event_catalog = pd.read_csv(DATA_SYNTHETIC / "synthetic_event_catalog.csv", parse_dates=["start_time", "end_time"])
            """
        ),
        md("## Step 1 - 建立多變量 window features"),
        code(
            """
            model_features = [
                "traffic_total", "ucast_total", "avg_packet_size", "error_rate",
                "discard_rate", "broadcast_ratio", "multicast_ratio", "unknown_total",
            ]

            window_rows = []
            for port_id, g in features.groupby("port_id", sort=False):
                g = g.sort_values("timestamp").set_index("timestamp")
                wf = g[["device_id", "port_id", "port_role", "event_label", "event_id"]].copy()
                generated = {}
                for col in model_features:
                    roll = g[col].rolling("30min", min_periods=3)
                    generated[f"{col}_mean_30m"] = roll.mean()
                    generated[f"{col}_std_30m"] = roll.std()
                    generated[f"{col}_max_30m"] = roll.max()
                    generated[f"{col}_min_30m"] = roll.min()
                    generated[f"{col}_p95_30m"] = roll.quantile(0.95)
                    generated[f"{col}_slope_30m"] = g[col].diff(6)
                wf = pd.concat([wf, pd.DataFrame(generated, index=wf.index)], axis=1)
                window_rows.append(wf.reset_index())

            windows = pd.concat(window_rows, ignore_index=True).fillna(0)
            X_cols = [c for c in windows.columns if c.endswith(("mean_30m", "std_30m", "max_30m", "min_30m", "p95_30m", "slope_30m"))]
            X = windows[X_cols].replace([np.inf, -np.inf], 0).fillna(0)
            print(windows.shape, len(X_cols))
            display(windows[["timestamp", "port_id", "event_label"] + X_cols[:6]].head())
            """
        ),
        md("## Step 2 - 訓練 Isolation Forest\n\n非監督式模型不需要 anomaly label，但 contamination 會影響異常比例。"),
        code(
            """
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import RobustScaler

            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X)
            model = IsolationForest(n_estimators=250, contamination=0.035, random_state=42)
            model.fit(X_scaled)
            windows["ml_anomaly_score"] = -model.score_samples(X_scaled)
            windows["ml_is_anomaly"] = model.predict(X_scaled) == -1
            windows["ml_method"] = "IsolationForest"

            display(windows.loc[windows["ml_is_anomaly"], ["timestamp", "port_id", "event_label", "ml_anomaly_score"]].head(12))
            """
        ),
        md("## Step 3 - 視覺化：anomaly score trend"),
        code(
            """
            port_id = "port-id7428"
            p = windows[windows["port_id"] == port_id].copy()
            threshold = windows["ml_anomaly_score"].quantile(0.965)

            fig, ax = plt.subplots(figsize=(14, 5))
            ax.plot(p["timestamp"], p["ml_anomaly_score"], label="ML anomaly score", linewidth=1)
            ax.axhline(threshold, color="tab:red", linestyle="--", label="global 96.5% threshold")
            v = p[p["ml_is_anomaly"]]
            ax.scatter(v["timestamp"], v["ml_anomaly_score"], color="tab:red", s=18, label="ML anomaly")
            for _, event in event_catalog.iterrows():
                if event["port_id"] in [port_id, "MULTI"]:
                    ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
            ax.set_title(f"{port_id} - Isolation Forest anomaly score")
            ax.legend(loc="upper left")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 4 - 視覺化：Top anomalous windows 與事件敏感度"),
        code(
            """
            top_windows = windows.sort_values("ml_anomaly_score", ascending=False).head(15)
            display(top_windows[["timestamp", "port_id", "event_label", "event_id", "ml_anomaly_score"]])

            event_score = (
                windows.groupby("event_label")
                .agg(avg_score=("ml_anomaly_score", "mean"), p95_score=("ml_anomaly_score", lambda s: s.quantile(0.95)), anomaly_rate=("ml_is_anomaly", "mean"), rows=("timestamp", "size"))
                .sort_values("p95_score", ascending=False)
            )
            display(event_score)

            fig, ax = plt.subplots(figsize=(12, 5))
            event_score["anomaly_rate"].sort_values().plot(kind="barh", ax=ax, color="tab:blue")
            ax.set_title("ML anomaly rate by simulated event")
            ax.set_xlabel("anomaly rate")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 5 - 簡易 feature contribution\n\nIsolation Forest 本身不是可解釋模型，這裡用 top anomalous windows 與全體 median 的 robust distance 作為教學用 contribution proxy。"),
        code(
            """
            top = windows[windows["ml_is_anomaly"]].copy()
            median = X.median()
            mad = (X - median).abs().median().replace(0, 1)
            contrib = ((top[X_cols] - median).abs() / mad).mean().sort_values(ascending=False).head(15)

            fig, ax = plt.subplots(figsize=(10, 6))
            contrib.sort_values().plot(kind="barh", ax=ax, color="tab:purple")
            ax.set_title("Proxy feature contribution among anomalous windows")
            ax.set_xlabel("mean robust distance")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        code(
            """
            output_cols = ["timestamp", "device_id", "port_id", "port_role", "event_label", "event_id", "ml_method", "ml_anomaly_score", "ml_is_anomaly"] + X_cols
            out_path = DATA_PROCESSED / "ml_anomaly_scores.csv"
            windows[output_cols].to_csv(out_path, index=False)
            print(f"saved: {out_path}")
            """
        ),
    ]


def notebook5() -> list[dict]:
    return [
        md("# Notebook5 - AD Alert Reduction\n\n把多個低階 anomaly flags 聚合為更少、更有語意的 alerts，降低告警疲勞。"),
        code(SETUP),
        code(
            """
            flags = pd.read_csv(DATA_PROCESSED / "baseline_anomaly_flags.csv", parse_dates=["timestamp"])
            display(flags.head())
            """
        ),
        md("## Step 1 - 將 anomaly flags 展開成 raw alerts"),
        code(
            """
            flag_to_metric = {
                "traffic_high": "traffic",
                "packets_high": "packets",
                "errors_high": "errors",
                "discards_high": "discards",
                "broadcast_high": "broadcast",
                "multicast_high": "multicast",
                "unknown_high": "unknown_protocol",
            }

            raw_rows = []
            for _, row in flags.iterrows():
                for flag, metric in flag_to_metric.items():
                    if bool(row[flag]):
                        raw_rows.append(
                            {
                                "timestamp": row["timestamp"],
                                "device_id": row["device_id"],
                                "port_id": row["port_id"],
                                "event_label": row["event_label"],
                                "event_id": row["event_id"],
                                "metric": metric,
                                "alert_name": flag,
                            }
                        )
            raw_alerts = pd.DataFrame(raw_rows)
            print(f"raw alerts: {len(raw_alerts):,}")
            display(raw_alerts.head(10))
            """
        ),
        md("## Step 2 - 視覺化：Raw alert volume\n\n這對應 Grafana 的 raw alert count panel。"),
        code(
            """
            alert_counts = raw_alerts.set_index("timestamp").resample("1h").size()
            fig, ax = plt.subplots(figsize=(14, 4))
            alert_counts.plot(ax=ax, color="tab:red", linewidth=1)
            ax.set_title("Raw alert count per hour")
            ax.set_ylabel("raw alerts")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 3 - 設計問題分類與 15 分鐘聚合規則"),
        code(
            """
            def classify_problem(metrics: set[str], affected_ports: int) -> str:
                if "broadcast" in metrics and affected_ports > 1:
                    return "Broadcast storm / L2 loop"
                if "multicast" in metrics and affected_ports > 1:
                    return "Multicast flooding"
                if {"traffic", "discards"}.issubset(metrics) and "errors" not in metrics:
                    return "Queue congestion"
                if "discards" in metrics:
                    return "Queue / buffer pressure"
                if "errors" in metrics and "traffic" not in metrics:
                    return "Link quality issue"
                if "unknown_protocol" in metrics:
                    return "Unknown protocol / scan"
                if "packets" in metrics and "traffic" in metrics:
                    return "Traffic or packet surge"
                if "packets" in metrics:
                    return "Packet surge / possible scan"
                if "traffic" in metrics:
                    return "Traffic surge / capacity pressure"
                if "broadcast" in metrics:
                    return "Broadcast anomaly"
                if "multicast" in metrics:
                    return "Multicast anomaly"
                return "General anomaly"


            raw_alerts = raw_alerts.sort_values(["port_id", "timestamp"])
            raw_alerts["bucket"] = raw_alerts["timestamp"].dt.floor("15min")
            reduced_rows = []
            for (bucket, alert_name), g in raw_alerts.groupby(["bucket", "alert_name"]):
                metrics = set(g["metric"])
                affected_ports = g["port_id"].nunique()
                severity = min(100, 20 + 8 * len(g) + 15 * affected_ports + 12 * len(metrics))
                reduced_rows.append(
                    {
                        "start_time": g["timestamp"].min(),
                        "end_time": g["timestamp"].max(),
                        "problem_type": classify_problem(metrics, affected_ports),
                        "affected_ports": ",".join(sorted(g["port_id"].unique())),
                        "affected_port_count": affected_ports,
                        "evidence_metrics": ",".join(sorted(metrics)),
                        "raw_alert_count": len(g),
                        "severity_score": severity,
                        "event_labels": ",".join(sorted(set(g["event_label"]))),
                    }
                )
            reduced = pd.DataFrame(reduced_rows).sort_values(["start_time", "severity_score"], ascending=[True, False])
            display(reduced.head(12))
            """
        ),
        md("## Step 4 - 視覺化：Raw vs Reduced、severity distribution、Top affected ports"),
        code(
            """
            fig, axes = plt.subplots(1, 3, figsize=(16, 4))
            pd.Series({"raw_alerts": len(raw_alerts), "reduced_alerts": len(reduced)}).plot(kind="bar", ax=axes[0], color=["tab:red", "tab:blue"])
            axes[0].set_title("Raw vs Reduced")
            axes[0].set_ylabel("count")

            reduced["severity_score"].plot(kind="hist", bins=20, ax=axes[1], color="tab:orange")
            axes[1].set_title("Severity distribution")

            top_ports = raw_alerts["port_id"].value_counts().head(8)
            top_ports.sort_values().plot(kind="barh", ax=axes[2], color="tab:green")
            axes[2].set_title("Top affected ports")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 5 - Alert timeline"),
        code(
            """
            timeline = reduced.copy()
            timeline["mid_time"] = timeline["start_time"] + (timeline["end_time"] - timeline["start_time"]) / 2
            types = {name: i for i, name in enumerate(sorted(timeline["problem_type"].unique()))}
            timeline["y"] = timeline["problem_type"].map(types)

            fig, ax = plt.subplots(figsize=(14, 6))
            scatter = ax.scatter(timeline["mid_time"], timeline["y"], s=timeline["severity_score"] * 2, c=timeline["severity_score"], cmap="viridis", alpha=0.75)
            ax.set_yticks(list(types.values()))
            ax.set_yticklabels(list(types.keys()))
            ax.set_title("Reduced alert timeline")
            ax.grid(alpha=0.25)
            plt.colorbar(scatter, ax=ax, label="severity")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        code(
            """
            raw_path = DATA_PROCESSED / "raw_alerts.csv"
            reduced_path = DATA_PROCESSED / "reduced_alerts.csv"
            raw_alerts.to_csv(raw_path, index=False)
            reduced.to_csv(reduced_path, index=False)
            print(f"saved: {raw_path}")
            print(f"saved: {reduced_path}")
            """
        ),
    ]


def notebook6() -> list[dict]:
    return [
        md("# Notebook6 - Forecasting\n\n用同時段 baseline 和 rolling residual 建立 prediction interval，進行 forecasting anomaly 和 capacity early warning。"),
        code(SETUP),
        code(
            """
            features = pd.read_csv(DATA_PROCESSED / "features.csv", parse_dates=["timestamp"])
            event_catalog = pd.read_csv(DATA_SYNTHETIC / "synthetic_event_catalog.csv", parse_dates=["start_time", "end_time"])
            """
        ),
        md("## Step 1 - 建立 forecast baseline 與 prediction interval"),
        code(
            """
            target = "traffic_total"
            rows = []
            for port_id, g in features.groupby("port_id", sort=False):
                g = g.sort_values("timestamp").copy()
                g["slot"] = g["timestamp"].dt.dayofweek.astype(str) + "-" + g["timestamp"].dt.hour.astype(str) + "-" + (g["timestamp"].dt.minute // 5).astype(str)
                seasonal = g.groupby("slot")[target].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
                moving = g[target].shift(1).rolling(12, min_periods=3).mean()
                g["y_hat"] = seasonal.fillna(moving).fillna(g[target].expanding().mean())
                residual = (g[target] - g["y_hat"]).abs()
                band = residual.shift(1).rolling(24, min_periods=6).quantile(0.95).fillna(residual.quantile(0.95))
                g["y_hat_lower"] = (g["y_hat"] - band).clip(lower=0)
                g["y_hat_upper"] = g["y_hat"] + band
                capacity = g[target].quantile(0.995) * 1.15
                g["capacity"] = capacity
                g["forecast_positive_anomaly"] = g[target] > g["y_hat_upper"]
                g["forecast_negative_anomaly"] = g[target] < g["y_hat_lower"]
                g["forecast_30m"] = g["y_hat"].shift(-6)
                g["early_warning_30m"] = g["forecast_30m"] > capacity * 0.80
                rows.append(g)

            forecast = pd.concat(rows, ignore_index=True)
            display(forecast[["timestamp", "port_id", target, "y_hat", "y_hat_lower", "y_hat_upper", "early_warning_30m"]].head())
            """
        ),
        md("## Step 2 - 視覺化：Actual vs Forecast + prediction interval"),
        code(
            """
            port_id = "port-id7431"
            p = forecast[forecast["port_id"] == port_id].copy()

            fig, ax = plt.subplots(figsize=(14, 5))
            ax.plot(p["timestamp"], p[target], label="actual", linewidth=1)
            ax.plot(p["timestamp"], p["y_hat"], label="forecast", linewidth=1.2)
            ax.fill_between(p["timestamp"], p["y_hat_lower"], p["y_hat_upper"], alpha=0.18, label="prediction interval")
            ax.plot(p["timestamp"], p["capacity"], label="capacity", color="tab:red", linestyle="--")
            warnings_df = p[p["early_warning_30m"]]
            ax.scatter(warnings_df["timestamp"], warnings_df[target], color="tab:orange", s=18, label="early warning")
            for _, event in event_catalog.iterrows():
                if event["port_id"] in [port_id, "MULTI"]:
                    ax.axvspan(event["start_time"], event["end_time"], alpha=0.10, color="tab:red")
            ax.set_title(f"{port_id} - Forecasting and capacity early warning")
            ax.legend(loc="upper left")
            ax.grid(alpha=0.25)
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 3 - 視覺化：Forecasting anomaly summary"),
        code(
            """
            summary = (
                forecast.groupby("event_label")
                .agg(
                    rows=("timestamp", "size"),
                    positive_anomaly=("forecast_positive_anomaly", "sum"),
                    negative_anomaly=("forecast_negative_anomaly", "sum"),
                    early_warning=("early_warning_30m", "sum"),
                )
            )
            summary["positive_rate"] = summary["positive_anomaly"] / summary["rows"]
            display(summary.sort_values("positive_rate", ascending=False))

            fig, ax = plt.subplots(figsize=(12, 5))
            summary["early_warning"].sort_values().plot(kind="barh", ax=ax, color="tab:orange")
            ax.set_title("Early warning count by event label")
            ax.set_xlabel("count")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        code(
            """
            keep = [
                "timestamp", "device_id", "port_id", "port_role", "event_label", "event_id",
                target, "y_hat_lower", "y_hat", "y_hat_upper", "capacity",
                "forecast_positive_anomaly", "forecast_negative_anomaly", "forecast_30m", "early_warning_30m",
            ]
            out_path = DATA_PROCESSED / "forecast_results.csv"
            forecast[keep].to_csv(out_path, index=False)
            print(f"saved: {out_path}")
            """
        ),
    ]


def notebook7() -> list[dict]:
    return [
        md("# Notebook7 - Root Cause Analysis with LLM\n\n整合 reduced alerts、metric interaction rules 與事件視窗 evidence，產生 RCA candidate ranking 和 LLM prompt。"),
        code(SETUP),
        code(
            """
            features = pd.read_csv(DATA_PROCESSED / "features.csv", parse_dates=["timestamp"])
            reduced = pd.read_csv(DATA_PROCESSED / "reduced_alerts.csv", parse_dates=["start_time", "end_time"])
            print(reduced.shape)
            display(reduced.head())
            """
        ),
        md("## Step 1 - 建立 RCA rules\n\n把 reduced alert 的 evidence metrics 轉成 root cause candidate。"),
        code(
            """
            def candidate_from_row(row):
                metrics = set(str(row.get("evidence_metrics", "")).split(","))
                problem = row.get("problem_type", "General anomaly")
                if "Queue congestion" in problem or "Queue / buffer" in problem:
                    return "Queue congestion / buffer pressure", [
                        "OCTETS high", "DISCARDS high", "ERRORS normal or not dominant",
                        "Check QoS, queue, bandwidth, top talkers, scheduled backup jobs",
                    ]
                if "Broadcast" in problem:
                    return "Broadcast storm / L2 loop", [
                        "BROADCAST high across ports", "NUCAST high may rise together",
                        "Check STP, loop, ARP storm, DHCP storm, VLAN scope",
                    ]
                if "Multicast" in problem:
                    return "Multicast flooding", [
                        "MULTICAST high across ports", "DISCARDS may rise",
                        "Check IGMP snooping, querier, IPTV or routing protocol behavior",
                    ]
                if "Link quality" in problem or "errors" in metrics:
                    return "Link quality issue", [
                        "ERRORS spike or repeated spikes", "Traffic may not be high",
                        "Check cable, SFP, NIC, port, duplex mismatch",
                    ]
                if "unknown_protocol" in metrics:
                    return "Unknown protocol / scan", [
                        "INUNKNOWNPROTOS high", "INPKTS high",
                        "Check non-standard protocol, scan, attack, VLAN/routing config, new device rollout",
                    ]
                if "Packet surge" in problem:
                    return "Small packet scan or connection surge", [
                        "UCASTPKTS high", "OCTETS may be flat or only mildly high",
                        "Check port scan, short connections, DDoS small packets, heartbeat surge",
                    ]
                if "Traffic surge" in problem:
                    return "Business traffic growth or large transfer", [
                        "OCTETS high", "Compare packet growth and avg_packet_size",
                        "Check backup, data sync, download, upload, streaming, or capacity pressure",
                    ]
                return "General network anomaly", ["Review metric trend, affected ports, recent changes"]
            """
        ),
        md("## Step 2 - 產生 RCA event table 與 scores"),
        code(
            """
            rca_rows = []
            for idx, row in reduced.iterrows():
                candidate, evidence = candidate_from_row(row)
                duration_minutes = max(5, int((row["end_time"] - row["start_time"]).total_seconds() / 60) + 5)
                score = min(100, int(row["severity_score"]) + 3 * len(evidence) + row["affected_port_count"] * 4)
                rca_rows.append(
                    {
                        "rca_event_id": f"RCA-{idx + 1:03d}",
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                        "affected_ports": row["affected_ports"],
                        "problem_type": row["problem_type"],
                        "root_cause_candidate": candidate,
                        "evidence": " | ".join(evidence),
                        "duration_minutes": duration_minutes,
                        "severity_score": row["severity_score"],
                        "root_cause_score": score,
                        "confidence": "High" if score >= 85 else "Medium" if score >= 65 else "Low",
                    }
                )

            rca = pd.DataFrame(rca_rows).sort_values(["root_cause_score", "start_time"], ascending=[False, True])
            display(rca.head(12))
            """
        ),
        md("## Step 3 - 視覺化：Root cause candidate ranking 與 confidence"),
        code(
            """
            candidate_summary = (
                rca.groupby("root_cause_candidate")
                .agg(events=("rca_event_id", "count"), avg_score=("root_cause_score", "mean"), max_score=("root_cause_score", "max"))
                .sort_values("events", ascending=False)
            )
            display(candidate_summary)

            fig, axes = plt.subplots(1, 2, figsize=(15, 5))
            candidate_summary["events"].sort_values().plot(kind="barh", ax=axes[0], color="tab:blue")
            axes[0].set_title("RCA candidate event count")
            axes[0].set_xlabel("events")

            rca["confidence"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0).plot(kind="bar", ax=axes[1], color="tab:green")
            axes[1].set_title("Confidence distribution")
            axes[1].set_ylabel("events")
            plt.tight_layout()
            show_fig(fig)
            """
        ),
        md("## Step 4 - 產生 LLM prompt 與 RCA report"),
        code(
            """
            def build_llm_prompt(event):
                lines = [
                    "你是一位 AIOps / Network RCA 助理。",
                    "請根據以下監控證據判斷可能根因，並輸出：",
                    "1. 問題型態",
                    "2. 主要證據",
                    "3. 可能根因",
                    "4. 建議處置",
                    "5. 信心分數",
                    "",
                    f"事件時間：{event.start_time} - {event.end_time}",
                    f"影響介面：{event.affected_ports}",
                    f"問題類型：{event.problem_type}",
                    f"RCA 候選：{event.root_cause_candidate}",
                    f"證據：{event.evidence}",
                    f"嚴重度：{event.severity_score}",
                    f"信心：{event.confidence}",
                ]
                return "\\n".join(lines)


            report_lines = [
                "# RCA Report",
                "",
                "本報告由 Notebook7 根據 reduced alerts 與 metric interaction rules 產生，可作為 LLM prompt 或人工診斷摘要。",
                "",
            ]
            for event in rca.head(12).itertuples(index=False):
                report_lines.extend(
                    [
                        f"## {event.rca_event_id} - {event.root_cause_candidate}",
                        "",
                        f"- 事件時間：{event.start_time} - {event.end_time}",
                        f"- 影響介面：{event.affected_ports}",
                        f"- 問題型態：{event.problem_type}",
                        f"- 主要證據：{event.evidence}",
                        f"- 根因分數：{event.root_cause_score}",
                        f"- 信心分數：{event.confidence}",
                        "",
                        "### LLM Prompt",
                        "",
                        "```text",
                        build_llm_prompt(event).strip(),
                        "```",
                        "",
                    ]
                )

            out_events = DATA_PROCESSED / "rca_events.csv"
            out_report = REPORTS / "rca_report.md"
            rca.to_csv(out_events, index=False)
            out_report.write_text("\\n".join(report_lines), encoding="utf-8")
            print(f"saved: {out_events}")
            print(f"saved: {out_report}")
            print("\\n".join(report_lines[:30]))
            """
        ),
        md("## Step 5 - RCA workflow 回顧\n\nMetrics → Time Window → Anomaly Flags → Metric Interaction Rules → Root Cause Candidate Ranking → LLM Explanation → Recommended Action"),
    ]


def main() -> None:
    notebooks = {
        "Notebook1_Time_Series_Features.ipynb": notebook1(),
        "Notebook2_Baseline_Anomaly_Detection.ipynb": notebook2(),
        "Notebook3_SPC_for_AD.ipynb": notebook3(),
        "Notebook4_ML_Unsupervised_for_AD.ipynb": notebook4(),
        "Notebook5_AD_Alert_Reduction.ipynb": notebook5(),
        "Notebook6_Forecasting.ipynb": notebook6(),
        "Notebook7_Root_Cause_Analysis_with_LLM.ipynb": notebook7(),
    }
    for name, cells in notebooks.items():
        write_notebook(ROOT / "notebooks" / name, cells)
    print(f"wrote {len(notebooks)} teaching notebooks")


if __name__ == "__main__":
    main()
