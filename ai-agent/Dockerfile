FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright と Chromium をインストール
RUN playwright install chromium --with-deps

COPY . .

RUN mkdir -p /app/reports

ENTRYPOINT ["python", "agent.py"]
