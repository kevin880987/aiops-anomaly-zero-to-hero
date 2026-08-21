FROM python:3.12.12-slim

# 這個 image 只裝重播程式需要的兩個套件。程式本體不 COPY 進來，
# 是 compose 把課程資料夾裡的 results_exporter.py 掛進來的 (compose.yaml 的 volumes
# 那一行寫著它的位置): 一份程式兩個地方用 (notebook 裡手動跑、compose 裡自動跑)，
# 行為才不會分岔。
RUN pip install --no-cache-dir "pandas>=2,<4" "prometheus_client>=0.20"

RUN useradd --create-home --uid 10001 lab07
WORKDIR /opt
USER 10001
EXPOSE 8010
CMD ["python", "/opt/app/results_exporter.py"]
