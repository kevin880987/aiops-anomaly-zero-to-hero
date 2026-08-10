FROM python:3.12.12-slim

RUN useradd --create-home --uid 10001 lab05 \
    && install -d -o lab05 -g lab05 /data
WORKDIR /app
COPY app.py /app/app.py
USER 10001
EXPOSE 9300
CMD ["python", "/app/app.py"]
