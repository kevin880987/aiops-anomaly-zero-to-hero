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
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(path: Path, cells: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=2), encoding="utf-8")


def simulator_cells() -> list[dict]:
    return [
        md(
            """
            # Simulator - Synthetic RRD-like Network Metrics

            依據「三、資料模擬設計構想」建立類似 LibreNMS / RRDTool / SNMP polling 的網路介面監控資料。

            設計重點：
            - 每 300 秒一筆，模擬 30 天資料。
            - 多個 device / port，各自有不同 baseline、In/Out 比例與平均封包大小。
            - 正常資料包含日週期、工作日/假日差異、隨機波動、正常業務尖峰。
            - 注入 Event A-J，讓後續 Notebook 能練習 AD、Alert Reduction、Forecasting 與 RCA。
            """
        ),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().resolve()
            while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "pyproject.toml").exists():
                PROJECT_ROOT = PROJECT_ROOT.parent
            if not (PROJECT_ROOT / "pyproject.toml").exists():
                raise FileNotFoundError("Run this notebook from inside the course repository.")

            RAW_DIR = PROJECT_ROOT / "data" / "synthetic"
            PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

            rng = np.random.default_rng(42)
            POLL_SECONDS = 300
            START = "2026-02-01 00:00:00"
            DAYS = 30
            timestamps = pd.date_range(START, periods=DAYS * 24 * 12, freq=f"{POLL_SECONDS}s")

            ports = pd.DataFrame(
                [
                    ("edge-fw-01", "port-id7427", "wan-primary", 6.8e7, 0.72, 900, 0.95),
                    ("edge-fw-01", "port-id7428", "wan-secondary", 2.6e7, 0.55, 820, 0.70),
                    ("core-sw-01", "port-id7429", "server-uplink", 8.2e7, 0.38, 1050, 1.15),
                    ("core-sw-01", "port-id7430", "office-vlan", 3.4e7, 0.64, 760, 0.82),
                    ("dist-sw-02", "port-id7431", "backup-storage", 4.8e7, 0.44, 1180, 1.05),
                ],
                columns=["device_id", "port_id", "port_role", "base_octets", "in_share", "avg_packet_size", "business_weight"],
            )
            ports
            """
        ),
        md(
            """
            ## 正常流量模型

            `traffic(t) = baseline + daily_seasonality + weekly_effect + random_noise`

            這裡用白天高峰、週末折減、lognormal 噪聲與少量正常尖峰來產生合理但不過度平滑的時間序列。
            """
        ),
        code(
            """
            def daily_profile(index: pd.DatetimeIndex) -> np.ndarray:
                hour = index.hour + index.minute / 60
                morning = np.exp(-0.5 * ((hour - 10.5) / 2.6) ** 2)
                afternoon = np.exp(-0.5 * ((hour - 15.5) / 3.2) ** 2)
                evening_low = 0.25 + 0.75 / (1 + np.exp(-(hour - 7)))
                night_drop = 0.35 + 0.65 / (1 + np.exp(hour - 21))
                return (0.45 + 0.40 * morning + 0.55 * afternoon) * evening_low * night_drop


            def weekly_profile(index: pd.DatetimeIndex) -> np.ndarray:
                is_weekend = index.dayofweek >= 5
                return np.where(is_weekend, 0.58, 1.0)


            def normal_spikes(n: int, probability: float = 0.006) -> np.ndarray:
                spikes = np.ones(n)
                starts = np.flatnonzero(rng.random(n) < probability)
                for start in starts:
                    width = int(rng.integers(1, 5))
                    multiplier = float(rng.uniform(1.15, 1.75))
                    spikes[start : start + width] *= multiplier
                return spikes


            def build_normal_port_series(port: pd.Series) -> pd.DataFrame:
                n = len(timestamps)
                seasonal = daily_profile(timestamps) * weekly_profile(timestamps)
                noise = rng.lognormal(mean=0.0, sigma=0.10, size=n)
                traffic = port.base_octets * port.business_weight * seasonal * noise * normal_spikes(n)
                traffic = np.maximum(traffic, port.base_octets * 0.04)

                asym = np.clip(port.in_share + rng.normal(0, 0.035, n), 0.18, 0.86)
                in_octets = traffic * asym
                out_octets = traffic * (1 - asym)

                packet_size = np.clip(rng.normal(port.avg_packet_size, port.avg_packet_size * 0.08, n), 220, 1450)
                in_ucast = in_octets / packet_size
                out_ucast = out_octets / packet_size

                nucast_base = np.maximum((in_ucast + out_ucast) * rng.uniform(0.008, 0.018), 1)
                broadcast_base = np.maximum((in_ucast + out_ucast) * rng.uniform(0.0015, 0.004), 0.2)
                multicast_base = np.maximum((in_ucast + out_ucast) * rng.uniform(0.002, 0.006), 0.2)

                df = pd.DataFrame(
                    {
                        "timestamp": timestamps,
                        "device_id": port.device_id,
                        "port_id": port.port_id,
                        "port_role": port.port_role,
                        "INOCTETS": in_octets,
                        "OUTOCTETS": out_octets,
                        "INERRORS": rng.poisson(0.015, n),
                        "OUTERRORS": rng.poisson(0.010, n),
                        "INUCASTPKTS": in_ucast,
                        "OUTUCASTPKTS": out_ucast,
                        "INNUCASTPKTS": nucast_base * rng.uniform(0.45, 0.60),
                        "OUTNUCASTPKTS": nucast_base * rng.uniform(0.40, 0.55),
                        "INDISCARDS": rng.poisson(0.04, n),
                        "OUTDISCARDS": rng.poisson(0.05, n),
                        "INUNKNOWNPROTOS": rng.poisson(0.01, n),
                        "INBROADCASTPKTS": broadcast_base * rng.uniform(0.50, 0.65),
                        "OUTBROADCASTPKTS": broadcast_base * rng.uniform(0.35, 0.50),
                        "INMULTICASTPKTS": multicast_base * rng.uniform(0.50, 0.65),
                        "OUTMULTICASTPKTS": multicast_base * rng.uniform(0.35, 0.50),
                    }
                )
                return df


            metrics = pd.concat([build_normal_port_series(row) for _, row in ports.iterrows()], ignore_index=True)
            metrics["event_label"] = "normal"
            metrics["event_id"] = ""
            metrics.head()
            """
        ),
        md(
            """
            ## 異常事件 A-J

            每個事件都透過多欄位同步變化呈現，以便後續區分「正常業務增加」與「故障異常」。
            """
        ),
        code(
            """
            event_specs = [
                ("A", "business_traffic_growth", "port-id7430", "2026-02-04 09:00", 24, "正常業務流量增加"),
                ("B", "small_packet_scan", "port-id7428", "2026-02-06 13:10", 10, "大量小封包 / 掃描"),
                ("C", "large_file_backup", "port-id7431", "2026-02-08 01:00", 36, "大檔案傳輸 / 備份"),
                ("D", "queue_congestion", "port-id7427", "2026-02-11 15:20", 14, "頻寬壅塞 / Queue 滿"),
                ("E", "link_quality_issue", "port-id7429", "2026-02-14 10:35", 8, "線路品質問題"),
                ("F", "load_sensitive_link_issue", "port-id7427", "2026-02-17 16:00", 18, "高負載下線路不穩"),
                ("G", "broadcast_storm", "MULTI", "2026-02-19 11:30", 12, "Broadcast Storm / L2 Loop"),
                ("H", "multicast_flooding", "MULTI", "2026-02-22 20:05", 18, "Multicast Flooding"),
                ("I", "abnormal_device_sender", "port-id7430", "2026-02-25 09:45", 16, "異常設備大量發送"),
                ("J", "unknown_protocol_scan", "port-id7428", "2026-02-27 14:15", 10, "Unknown Protocol"),
            ]


            def event_mask(df: pd.DataFrame, port_id: str, start: str, periods: int) -> pd.Series:
                start_ts = pd.Timestamp(start)
                end_ts = start_ts + pd.Timedelta(minutes=5 * (periods - 1))
                time_mask = df["timestamp"].between(start_ts, end_ts)
                if port_id == "MULTI":
                    return time_mask
                return time_mask & (df["port_id"] == port_id)


            def apply_event(df: pd.DataFrame, spec: tuple[str, str, str, str, int, str]) -> None:
                event_id, event_type, port_id, start, periods, description = spec
                mask = event_mask(df, port_id, start, periods)
                idx = df.index[mask]
                if len(idx) == 0:
                    return

                ramp = np.linspace(0.8, 1.0, len(idx))
                df.loc[idx, "event_label"] = event_type
                df.loc[idx, "event_id"] = event_id

                if event_id == "A":
                    df.loc[idx, ["INOCTETS", "OUTOCTETS", "INUCASTPKTS", "OUTUCASTPKTS"]] *= 1.9
                elif event_id == "B":
                    df.loc[idx, ["INUCASTPKTS", "OUTUCASTPKTS"]] *= 8.0
                    df.loc[idx, ["INOCTETS", "OUTOCTETS"]] *= 1.25
                elif event_id == "C":
                    df.loc[idx, ["INOCTETS", "OUTOCTETS"]] *= 5.2
                    df.loc[idx, ["INUCASTPKTS", "OUTUCASTPKTS"]] *= 2.0
                elif event_id == "D":
                    df.loc[idx, ["INOCTETS", "OUTOCTETS", "INUCASTPKTS", "OUTUCASTPKTS"]] *= 3.8
                    discard_spike = np.round(600 * ramp + rng.normal(0, 30, len(idx))).clip(80)
                    df.loc[idx, ["INDISCARDS", "OUTDISCARDS"]] += np.column_stack([discard_spike, discard_spike])
                elif event_id == "E":
                    error_spike = rng.poisson(180, (len(idx), 2)) + np.round(100 * ramp)[:, None]
                    df.loc[idx, ["INERRORS", "OUTERRORS"]] += error_spike
                elif event_id == "F":
                    df.loc[idx, ["INOCTETS", "OUTOCTETS"]] *= 2.8
                    late = idx[int(len(idx) * 0.35) :]
                    error_spike = (
                        rng.poisson(120, (len(late), 2))
                        + np.round(120 * np.linspace(0.5, 1.2, len(late)))[:, None]
                    )
                    df.loc[late, ["INERRORS", "OUTERRORS"]] += error_spike
                elif event_id == "G":
                    df.loc[idx, ["INBROADCASTPKTS", "OUTBROADCASTPKTS", "INNUCASTPKTS", "OUTNUCASTPKTS"]] *= 18
                    df.loc[idx, ["INDISCARDS", "OUTDISCARDS"]] += rng.poisson(80, (len(idx), 2))
                elif event_id == "H":
                    df.loc[idx, ["INMULTICASTPKTS", "OUTMULTICASTPKTS"]] *= 16
                    df.loc[idx, ["INDISCARDS", "OUTDISCARDS"]] += rng.poisson(45, (len(idx), 2))
                elif event_id == "I":
                    df.loc[idx, ["OUTOCTETS", "OUTUCASTPKTS", "OUTNUCASTPKTS"]] *= 5.5
                    df.loc[idx, ["OUTBROADCASTPKTS", "OUTMULTICASTPKTS"]] *= 2.5
                elif event_id == "J":
                    df.loc[idx, "INUNKNOWNPROTOS"] += rng.poisson(360, len(idx)) + 80
                    df.loc[idx, "INUCASTPKTS"] *= 2.4


            for spec in event_specs:
                apply_event(metrics, spec)

            event_catalog = pd.DataFrame(
                event_specs,
                columns=["event_id", "event_type", "port_id", "start_time", "periods_5min", "description"],
            )
            event_catalog["end_time"] = pd.to_datetime(event_catalog["start_time"]) + pd.to_timedelta((event_catalog["periods_5min"] - 1) * 5, unit="m")
            event_catalog
            """
        ),
        code(
            """
            metric_columns = [
                "INOCTETS", "OUTOCTETS",
                "INERRORS", "OUTERRORS",
                "INUCASTPKTS", "OUTUCASTPKTS",
                "INNUCASTPKTS", "OUTNUCASTPKTS",
                "INDISCARDS", "OUTDISCARDS",
                "INUNKNOWNPROTOS",
                "INBROADCASTPKTS", "OUTBROADCASTPKTS",
                "INMULTICASTPKTS", "OUTMULTICASTPKTS",
            ]

            metrics[metric_columns] = metrics[metric_columns].clip(lower=0)
            counter_like = [c for c in metric_columns if c not in ["INOCTETS", "OUTOCTETS"]]
            metrics[counter_like] = metrics[counter_like].round().astype(int)
            metrics[["INOCTETS", "OUTOCTETS"]] = metrics[["INOCTETS", "OUTOCTETS"]].round(2)

            metrics = metrics.sort_values(["device_id", "port_id", "timestamp"]).reset_index(drop=True)
            metrics.to_csv(RAW_DIR / "synthetic_rrd_metrics.csv", index=False)
            event_catalog.to_csv(RAW_DIR / "synthetic_event_catalog.csv", index=False)

            print(f"rows: {len(metrics):,}")
            print(f"ports: {metrics['port_id'].nunique()}")
            print(f"time range: {metrics['timestamp'].min()} -> {metrics['timestamp'].max()}")
            print(f"saved: {RAW_DIR / 'synthetic_rrd_metrics.csv'}")
            metrics.groupby("event_label").size().sort_values(ascending=False)
            """
        ),
        code(
            """
            sample_port = "port-id7427"
            plot_df = metrics[metrics["port_id"] == sample_port].copy()
            plot_df["traffic_total"] = plot_df["INOCTETS"] + plot_df["OUTOCTETS"]
            plot_df["errors_total"] = plot_df["INERRORS"] + plot_df["OUTERRORS"]
            plot_df["discards_total"] = plot_df["INDISCARDS"] + plot_df["OUTDISCARDS"]

            try:
                import matplotlib.pyplot as plt

                fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
                axes[0].plot(plot_df["timestamp"], plot_df["traffic_total"], label="traffic_total")
                axes[1].plot(plot_df["timestamp"], plot_df["errors_total"], color="tab:red", label="errors_total")
                axes[2].plot(plot_df["timestamp"], plot_df["discards_total"], color="tab:orange", label="discards_total")
                for ax in axes:
                    ax.legend(loc="upper left")
                    ax.grid(alpha=0.25)
                fig.suptitle(f"Synthetic RRD-like metrics - {sample_port}")
                plt.tight_layout()
            except ImportError:
                display_cols = ["timestamp", "traffic_total", "errors_total", "discards_total", "event_label"]
                print("matplotlib not installed; showing event-window sample instead.")
                plot_df.loc[plot_df["event_label"] != "normal", display_cols].head(12)
            """
        ),
    ]


def notebook1_cells() -> list[dict]:
    return [
        md("# Notebook1 - Time Series Features\n\n將 raw RRD-like metrics 轉換成 rolling statistics、lag、rate 與 ratio features。"),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            RAW = PROJECT_ROOT / "data" / "synthetic" / "synthetic_rrd_metrics.csv"
            OUT = PROJECT_ROOT / "data" / "processed" / "features.csv"
            df = pd.read_csv(RAW, parse_dates=["timestamp"]).sort_values(["device_id", "port_id", "timestamp"])
            df.head()
            """
        ),
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
            df[["traffic_total", "ucast_total", "avg_packet_size", "error_rate", "discard_rate"]].describe()
            """
        ),
        code(
            """
            def rolling_mad(series):
                median = np.median(series)
                return np.median(np.abs(series - median))


            feature_frames = []
            base_features = [
                "traffic_total", "ucast_total", "errors_total", "discards_total",
                "broadcast_total", "multicast_total", "unknown_total",
                "avg_packet_size", "error_rate", "discard_rate", "broadcast_ratio", "multicast_ratio",
            ]

            for (_, port_id), g in df.groupby(["device_id", "port_id"], sort=False):
                g = g.sort_values("timestamp").set_index("timestamp")
                for col in base_features:
                    g[f"{col}_rolling_mean_1h"] = g[col].rolling("60min", min_periods=3).mean()
                    g[f"{col}_rolling_std_1h"] = g[col].rolling("60min", min_periods=3).std()
                    g[f"{col}_rolling_median_1h"] = g[col].rolling("60min", min_periods=3).median()
                    g[f"{col}_rolling_p95_1d"] = g[col].rolling("1D", min_periods=12).quantile(0.95)
                    g[f"{col}_rolling_mad_1d"] = g[col].rolling("1D", min_periods=12).apply(rolling_mad, raw=True)
                    g[f"{col}_lag_5m"] = g[col].shift(1)
                    g[f"{col}_lag_1h"] = g[col].shift(12)
                feature_frames.append(g.reset_index())

            features = pd.concat(feature_frames, ignore_index=True)
            features = features.bfill().fillna(0)
            features.to_csv(OUT, index=False)
            print(f"saved: {OUT}")
            features.head()
            """
        ),
    ]


def notebook2_cells() -> list[dict]:
    return [
        md("# Notebook2 - Baseline Anomaly Detection\n\n用 rolling baseline、MAD 與 percentile threshold 建立可解釋的異常 flags。"),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "features.csv", parse_dates=["timestamp"])
            OUT = PROJECT_ROOT / "data" / "processed" / "baseline_anomaly_flags.csv"
            """
        ),
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
            result.to_csv(OUT, index=False)
            print(f"saved: {OUT}")
            result[result["any_baseline_anomaly"]].head(10)
            """
        ),
    ]


def notebook3_cells() -> list[dict]:
    return [
        md("# Notebook3 - SPC for AD\n\n用 Shewhart、EWMA、CUSUM 控制圖觀察 traffic、discard_rate、error_rate。"),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "features.csv", parse_dates=["timestamp"])
            OUT = PROJECT_ROOT / "data" / "processed" / "spc_results.csv"
            """
        ),
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
                pos = []
                s = 0.0
                for value in g["error_rate"].fillna(0):
                    s = max(0, s + value - error_mu - k)
                    pos.append(s)
                g["cusum_error_pos"] = pos
                g["cusum_error_h"] = h
                g["cusum_error_violation"] = g["cusum_error_pos"] > h
                rows.append(g)

            spc = pd.concat(rows, ignore_index=True)
            spc["any_spc_violation"] = spc[["shewhart_traffic_violation", "ewma_discard_violation", "cusum_error_violation"]].any(axis=1)
            keep = [
                "timestamp", "device_id", "port_id", "port_role", "event_label", "event_id",
                "traffic_total", "traffic_center", "traffic_ucl", "traffic_lcl", "shewhart_traffic_violation",
                "discard_rate", "ewma_discard_rate", "ewma_discard_ucl", "ewma_discard_violation",
                "error_rate", "cusum_error_pos", "cusum_error_h", "cusum_error_violation", "any_spc_violation",
            ]
            spc[keep].to_csv(OUT, index=False)
            print(f"saved: {OUT}")
            spc.loc[spc["any_spc_violation"], keep].head(10)
            """
        ),
    ]


def notebook4_cells() -> list[dict]:
    return [
        md("# Notebook4 - ML Unsupervised for AD\n\n建立多變量 feature matrix 與 sliding-window 特徵，使用 Isolation Forest；若環境沒有 sklearn，改用 robust aggregate score。"),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "features.csv", parse_dates=["timestamp"])
            OUT = PROJECT_ROOT / "data" / "processed" / "ml_anomaly_scores.csv"
            """
        ),
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
                for col in model_features:
                    roll = g[col].rolling("30min", min_periods=3)
                    wf[f"{col}_mean_30m"] = roll.mean()
                    wf[f"{col}_std_30m"] = roll.std()
                    wf[f"{col}_max_30m"] = roll.max()
                    wf[f"{col}_min_30m"] = roll.min()
                    wf[f"{col}_p95_30m"] = roll.quantile(0.95)
                    wf[f"{col}_slope_30m"] = g[col].diff(6)
                window_rows.append(wf.reset_index())

            windows = pd.concat(window_rows, ignore_index=True).fillna(0)
            X_cols = [c for c in windows.columns if c.endswith(("mean_30m", "std_30m", "max_30m", "min_30m", "p95_30m", "slope_30m"))]
            X = windows[X_cols].replace([np.inf, -np.inf], 0).fillna(0)
            """
        ),
        code(
            """
            try:
                from sklearn.ensemble import IsolationForest
                from sklearn.preprocessing import RobustScaler

                scaler = RobustScaler()
                X_scaled = scaler.fit_transform(X)
                model = IsolationForest(n_estimators=200, contamination=0.035, random_state=42)
                model.fit(X_scaled)
                windows["ml_anomaly_score"] = -model.score_samples(X_scaled)
                windows["ml_is_anomaly"] = model.predict(X_scaled) == -1
                windows["ml_method"] = "IsolationForest"
            except Exception as exc:
                median = X.median()
                mad = (X - median).abs().median().replace(0, 1)
                robust_z = ((X - median).abs() / mad).clip(upper=25)
                windows["ml_anomaly_score"] = robust_z.mean(axis=1)
                threshold = windows["ml_anomaly_score"].quantile(0.965)
                windows["ml_is_anomaly"] = windows["ml_anomaly_score"] >= threshold
                windows["ml_method"] = f"robust_z_fallback: {exc.__class__.__name__}"

            output_cols = ["timestamp", "device_id", "port_id", "port_role", "event_label", "event_id", "ml_method", "ml_anomaly_score", "ml_is_anomaly"] + X_cols
            windows[output_cols].to_csv(OUT, index=False)
            print(f"saved: {OUT}")
            windows.loc[windows["ml_is_anomaly"], output_cols[:9]].head(10)
            """
        ),
    ]


def notebook5_cells() -> list[dict]:
    return [
        md("# Notebook5 - AD Alert Reduction\n\n把低階 anomaly flags 轉為 raw alerts，再依 port、問題型態與時間窗合併為 reduced alerts。"),
        code(
            """
            from pathlib import Path
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            flags = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "baseline_anomaly_flags.csv", parse_dates=["timestamp"])
            RAW_ALERTS = PROJECT_ROOT / "data" / "processed" / "raw_alerts.csv"
            REDUCED_ALERTS = PROJECT_ROOT / "data" / "processed" / "reduced_alerts.csv"
            """
        ),
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
            raw_alerts.to_csv(RAW_ALERTS, index=False)
            print(f"raw alerts: {len(raw_alerts):,}")
            """
        ),
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
                if "packets" in metrics and "traffic" in metrics:
                    return "Traffic or packet surge"
                if "unknown_protocol" in metrics:
                    return "Unknown protocol / scan"
                if "broadcast" in metrics:
                    return "Broadcast anomaly"
                if "multicast" in metrics:
                    return "Multicast anomaly"
                if "packets" in metrics:
                    return "Packet surge / possible scan"
                if "traffic" in metrics:
                    return "Traffic surge / capacity pressure"
                return "General anomaly"


            if raw_alerts.empty:
                reduced = pd.DataFrame()
            else:
                raw_alerts = raw_alerts.sort_values(["port_id", "timestamp"])
                raw_alerts["bucket"] = raw_alerts["timestamp"].dt.floor("15min")
                grouped = raw_alerts.groupby(["bucket", "alert_name"], as_index=False)
                reduced_rows = []
                for (_, _), g in grouped:
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

            reduced.to_csv(REDUCED_ALERTS, index=False)
            print(f"saved: {RAW_ALERTS}")
            print(f"saved: {REDUCED_ALERTS}")
            reduced.head(10)
            """
        ),
    ]


def notebook6_cells() -> list[dict]:
    return [
        md("# Notebook6 - Forecasting\n\n用同時段 baseline 與 rolling residual 建立 forecast、prediction interval 與 capacity early warning。"),
        code(
            """
            from pathlib import Path
            import numpy as np
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "features.csv", parse_dates=["timestamp"])
            OUT = PROJECT_ROOT / "data" / "processed" / "forecast_results.csv"
            """
        ),
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
            keep = [
                "timestamp", "device_id", "port_id", "port_role", "event_label", "event_id",
                target, "y_hat_lower", "y_hat", "y_hat_upper", "capacity",
                "forecast_positive_anomaly", "forecast_negative_anomaly", "forecast_30m", "early_warning_30m",
            ]
            forecast[keep].to_csv(OUT, index=False)
            print(f"saved: {OUT}")
            forecast.loc[forecast["early_warning_30m"], keep].head(10)
            """
        ),
    ]


def notebook7_cells() -> list[dict]:
    return [
        md("# Notebook7 - Root Cause Analysis with LLM\n\n整合 reduced alerts 與事件視窗 evidence，先用規則產生 RCA 候選，再輸出可交給 LLM 的 prompt 與 Markdown report。"),
        code(
            """
            from pathlib import Path
            import pandas as pd

            PROJECT_ROOT = Path.cwd().parents[0] if Path.cwd().name == "notebooks" else Path.cwd()
            features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "features.csv", parse_dates=["timestamp"])
            reduced = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "reduced_alerts.csv", parse_dates=["start_time", "end_time"])
            OUT_EVENTS = PROJECT_ROOT / "data" / "processed" / "rca_events.csv"
            OUT_REPORT = PROJECT_ROOT / "reports" / "rca_report.md"
            OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
            """
        ),
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
                if "Broadcast anomaly" in problem:
                    return "Broadcast storm risk", [
                        "BROADCAST packets high", "Check whether multiple ports rise together",
                        "Check ARP storm, DHCP storm, loop, STP, VLAN scope",
                    ]
                if "Multicast anomaly" in problem:
                    return "Multicast flooding risk", [
                        "MULTICAST packets high", "Check whether multiple ports rise together",
                        "Check IGMP snooping, querier, IPTV, routing protocol behavior",
                    ]
                if "packets" in metrics and "traffic" in metrics:
                    return "Small packet scan or traffic surge", [
                        "UCASTPKTS high", "Compare avg_packet_size and OCTETS",
                        "Check short connections, scan, DDoS, heartbeat surge",
                    ]
                return "General network anomaly", ["Review metric trend, affected ports, recent changes"]


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
            rca.to_csv(OUT_EVENTS, index=False)
            print(f"saved: {OUT_EVENTS}")
            rca.head(10)
            """
        ),
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

            OUT_REPORT.write_text("\\n".join(report_lines), encoding="utf-8")
            print(f"saved: {OUT_REPORT}")
            print("\\n".join(report_lines[:28]))
            """
        ),
    ]


def write_readme() -> None:
    content = """# Network Monitoring AIOps

以網路介面監控資料為主軸，建立 RRD / SNMP 類型 metrics 的 AIOps 教學專案。

## Data Flow

```text
Synthetic RRD-like Network Metrics
  -> Notebook1: Time Series Features
  -> Notebook2: Baseline Anomaly Detection
  -> Notebook3: SPC for AD
  -> Notebook4: ML Unsupervised for AD
  -> Notebook5: AD Alert Reduction
  -> Notebook6: Forecasting
  -> Notebook7: Root Cause Analysis with LLM
```

## 建議執行順序

1. `data/synthetic/simulator_rrd_metrics.ipynb`
2. `notebooks/Notebook1_Time_Series_Features.ipynb`
3. `notebooks/Notebook2_Baseline_Anomaly_Detection.ipynb`
4. `notebooks/Notebook3_SPC_for_AD.ipynb`
5. `notebooks/Notebook4_ML_Unsupervised_for_AD.ipynb`
6. `notebooks/Notebook5_AD_Alert_Reduction.ipynb`
7. `notebooks/Notebook6_Forecasting.ipynb`
8. `notebooks/Notebook7_Root_Cause_Analysis_with_LLM.ipynb`

## 補充教材

`course_materials/` 收錄原始網路介面監控教學文件，可搭配 Notebook 實作使用：

- `course_materials/01_網路介面監控_欄位說明.md`：說明 RRD / SNMP 監控欄位與網路介面 metrics 意義。
- `course_materials/02_網路介面監控_單一欄位異常.md`：說明單一欄位異常的判讀方式。
- `course_materials/03_網路介面監控_多欄位交互作用.md`：說明多欄位交互作用與異常型態。
- `course_materials/04_網路介面監控_RCA根本原因分析流程.md`：說明 RCA 根本原因分析流程。
- `course_materials/05_網路介面監控_實作教學設計.md`：說明本系列實作課程的教學設計。

`course_materials/images/` 收錄對應圖檔：

- `網路介面監控_欄位說明.png`
- `網路介面監控一欄位.png`
- `網路介面監控多欄位.png`
- `網路介面監控RCA.png`

## 三竹範例資料

`data/sample/mitake_error_log/` 收錄三竹提供的 LibreNMS / RRDTool sample data：

- `data/sample/mitake_error_log/read_rrd.ipynb`：讀取 RRD 的範例 Notebook，已改為專案相對路徑。
- `data/sample/mitake_error_log/rrd_helper.py`：以系統 `rrdtool` 包裝 `info` 與 `fetch`。
- `data/sample/mitake_error_log/資訊部/LibreNMS網路監控/Firewall_RRD_Log(Triggered off)/*.rrd`：5 個 firewall port RRD 檔。

讀取 `.rrd` 需要本機安裝 RRDtool：

```bash
brew install rrdtool
```

已驗證 5 個 sample RRD 檔皆可讀，解析度為 300 秒，並包含 15 個網路介面監控欄位。

## 環境設定

本專案使用 Python 虛擬環境 `.venv`，必要套件列在 `requirements.txt`。

### 1. 建立虛擬環境

```bash
python3 -m venv .venv
```

### 2. 啟用虛擬環境

```bash
source .venv/bin/activate
```

### 3. 安裝套件

```bash
python -m pip install -r requirements.txt
```

### 4. 設定繪圖 cache

若使用者家目錄的 Matplotlib / Fontconfig cache 不可寫，請將 cache 指到專案內：

```bash
mkdir -p .cache/matplotlib .cache/fontconfig
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
```

若在 terminal 或 CI 這類無視窗環境執行 notebook，可再加上：

```bash
export MPLBACKEND=Agg
```

### 5. 啟動 JupyterLab

```bash
jupyter lab
```

啟動後依照「建議執行順序」由資料模擬 notebook 開始執行。

### 已安裝並驗證的核心套件

- `numpy`
- `pandas`
- `matplotlib`
- `scikit-learn`
- `jupyterlab`
- `ipykernel`

## 主要產出

- `data/synthetic/synthetic_rrd_metrics.csv`
- `data/synthetic/synthetic_event_catalog.csv`
- `data/processed/features.csv`
- `data/processed/baseline_anomaly_flags.csv`
- `data/processed/spc_results.csv`
- `data/processed/ml_anomaly_scores.csv`
- `data/processed/raw_alerts.csv`
- `data/processed/reduced_alerts.csv`
- `data/processed/forecast_results.csv`
- `data/processed/rca_events.csv`
- `reports/rca_report.md`
"""
    (ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    for directory in [
        ROOT / "data" / "synthetic",
        ROOT / "data" / "processed",
        ROOT / "notebooks",
        ROOT / "grafana" / "dashboards",
        ROOT / "grafana" / "provisioning",
        ROOT / "reports",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    write_notebook(ROOT / "data" / "synthetic" / "simulator_rrd_metrics.ipynb", simulator_cells())
    write_notebook(ROOT / "notebooks" / "Notebook1_Time_Series_Features.ipynb", notebook1_cells())
    write_notebook(ROOT / "notebooks" / "Notebook2_Baseline_Anomaly_Detection.ipynb", notebook2_cells())
    write_notebook(ROOT / "notebooks" / "Notebook3_SPC_for_AD.ipynb", notebook3_cells())
    write_notebook(ROOT / "notebooks" / "Notebook4_ML_Unsupervised_for_AD.ipynb", notebook4_cells())
    write_notebook(ROOT / "notebooks" / "Notebook5_AD_Alert_Reduction.ipynb", notebook5_cells())
    write_notebook(ROOT / "notebooks" / "Notebook6_Forecasting.ipynb", notebook6_cells())
    write_notebook(ROOT / "notebooks" / "Notebook7_Root_Cause_Analysis_with_LLM.ipynb", notebook7_cells())
    write_readme()

    print(f"Generated project under {ROOT}")


if __name__ == "__main__":
    main()
