"""Names shared by the exporter and everything that queries it.

The exporter publishes a metric; dashboards, alert rules and notebooks query it
by name. Those are separate programs, so nothing makes them agree except that
the strings match. When they stop matching, no error is raised anywhere: the
exporter serves happily, Prometheus scrapes happily, and the panels are simply
empty. That is the same silent failure this workshop spends an afternoon
teaching people to recognise, so it should not be built into the tooling.

This module is deliberately dependency-free and lives outside the aiopskit
package, so that `python_results_exporter.py` can import it without pulling in
pandas plotting stacks it does not need.
"""
from __future__ import annotations

# The metric every notebook result is published as.
RESULT_METRIC = "aiops_python_result"
RESULT_TIMESTAMP_METRIC = "aiops_python_result_timestamp"

# Exporter self-reporting, read by the Lab 00 health tiles.
REPLAY_PROGRESS_METRIC = "aiops_replay_progress"
REPLAY_SPEED_METRIC = "aiops_replay_speed_x"
RESULT_ROWS_METRIC = "aiops_result_rows"

METRIC_HELP = {
    RESULT_METRIC: "Notebook-generated AIOps result exposed for Grafana.",
    RESULT_TIMESTAMP_METRIC: "Current simulated timestamp for Python result exporter.",
    REPLAY_PROGRESS_METRIC: "Position of the replay through the result CSV, 0 at the first row and 1 at the last.",
    REPLAY_SPEED_METRIC: "Simulated seconds advanced per real second.",
    RESULT_ROWS_METRIC: "Rows in the currently loaded result CSV.",
}

# Prometheus scrape job that must exist for any of this to reach Grafana.
EXPORTER_JOB = "python-results-exporter"

# Drop-zone filenames. The exporter watches these; aiopskit.grafana writes them.
DROPZONE_DIRNAME = "prometheus-dropzone"
RESULT_CSV_NAME = "current_results.csv"
RESULT_MANIFEST_NAME = "current_results.manifest.json"
REPLAY_STATE_NAME = "replay_state.json"

# Labels carried on every published series.
LABEL_COLUMNS = ["device_id", "port_id", "port_role", "event_label", "ml_method"]
