"""
aiops-monitor: AIOps pipeline for network interface monitoring.

Modules
-------
aiops_monitor.simulator.rrd     — synthetic RRD-like metric generation
aiops_monitor.anomaly.baseline  — statistical baseline anomaly detection
aiops_monitor.anomaly.spc       — SPC control-chart anomaly detection
aiops_monitor.anomaly.ml        — unsupervised ML anomaly detection
aiops_monitor.exporter          — Prometheus metrics exporter
"""

__version__ = "0.1.0"
