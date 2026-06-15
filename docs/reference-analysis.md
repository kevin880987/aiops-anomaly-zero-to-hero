# Reference Analysis and Course Positioning

This document records what the course learns from two public repositories and where it deliberately takes a different path. It is a design record, not learner-facing course material.

## Reference snapshots

During course development, the repositories were inspected as separate sibling clones. They are not vendored into this Git history.

| Repository | Snapshot inspected | Useful patterns |
| --- | --- | --- |
| [blueswen/grafana-zero-to-hero](https://github.com/blueswen/grafana-zero-to-hero) | `2023f6b` | Small Docker Compose labs, provisioned dashboards, broad Grafana coverage, operational use cases |
| [iam-veeramalla/observability-zero-to-hero](https://github.com/iam-veeramalla/observability-zero-to-hero) | `9445b23` | Clear day-based progression, Kubernetes monitoring, PromQL, logging, tracing, OpenTelemetry |

The snapshots identify the source state used for analysis. Before adopting a new technical pattern, inspect the current upstream repository and its license again.

## What the references do well

### Grafana Zero to Hero

The repository makes individual topics runnable. Its strongest teaching pattern is a small, self-contained lab with Docker Compose, provisioning, an architecture image, and direct links to the running services. It also extends beyond dashboards into plugins, alerting, management, infrastructure as code, and applied use cases.

### Observability Zero to Hero

The repository gives learners a recognizable sequence from fundamentals through metrics, logs, traces, and OpenTelemetry. Kubernetes manifests and Helm commands make the operational context concrete. The seven-day structure also makes course progress easy to communicate.

## Gaps this course will address

The references teach observability platforms, but neither provides a complete network-monitoring AIOps path from raw RRD/SNMP-like telemetry to operational decisions. This course will connect the platform layer to:

- network-specific metric semantics;
- reproducible congestion, packet-loss, error, and drop scenarios;
- time-series feature engineering;
- statistical and unsupervised anomaly detection;
- alert grouping and reduction;
- capacity forecasting;
- evidence-grounded root-cause analysis;
- a capstone that joins dashboards, alerts, model outputs, and an incident report.

The beginner path will run locally before introducing Kubernetes. This reduces setup risk while preserving a later route to production architecture.

## Quality targets

The course should compete on measurable teaching quality rather than repository size.

| Target | Acceptance condition |
| --- | --- |
| Fast first success | A learner with Docker can reach a populated dashboard with one command |
| Reproducible incidents | Each operational lab can generate a known failure condition on demand or on a documented cycle |
| Explicit verification | Every lab states what to query, what should appear, and how to detect setup failure |
| Traceable reasoning | Every anomaly, alert, and RCA statement points back to metrics or events |
| Progressive difficulty | Core labs require no cloud account; Kubernetes and OpenTelemetry are advanced modules |
| Operational closure | Labs include teardown, troubleshooting, and retained artifacts |
| Tested material | Scripts have automated checks; Compose and dashboards are validated in CI or a documented release check |

## Independence rule

Use the references to compare scope, sequencing, and learner ergonomics. Do not copy their prose, diagrams, dashboards, manifests, or code unless the license permits it and attribution is recorded. Prefer original network scenarios and original exercises because they are the course's main technical contribution.

## Review cadence

Review the references before each major course release. Record a new snapshot only when the analysis changes. Do not add timestamped copies of either repository to this course.
