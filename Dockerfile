FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:. \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Vaduz

LABEL maintainer="Peter Siebler <peter.siebler@gmail.com>" \
      application="hc_med"  \
      com.centurylinklabs.watchtower.enable="false" \
      dockhand.check-update="false"  \
      dockhand.ignore="true"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/logs

EXPOSE 5065

HEALTHCHECK --interval=60s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:5065/api/status || exit 1

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "5065", "--no-access-log"]
