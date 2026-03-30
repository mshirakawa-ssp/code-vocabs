FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY generate_report.sh /app/generate_report.sh
COPY templates/ /app/templates/
RUN chmod +x /app/generate_report.sh

RUN mkdir -p /app/reports

ENTRYPOINT ["/app/generate_report.sh"]
