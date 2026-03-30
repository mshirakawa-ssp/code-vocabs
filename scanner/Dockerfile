FROM python:3.11-slim

# git と semgrep の依存を含む軽量イメージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir semgrep

WORKDIR /app

COPY scan.sh /app/scan.sh
RUN chmod +x /app/scan.sh

RUN mkdir -p /app/reports

ENTRYPOINT ["/app/scan.sh"]
