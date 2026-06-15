FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV CSV_PATH=/data/synthetic/synthetic_rrd_metrics.csv
ENV EXPORTER_PORT=8000
ENV REPLAY_SPEED_X=60
ENV SCRAPE_INTERVAL_S=5

EXPOSE 8000

CMD ["aiops-export"]
