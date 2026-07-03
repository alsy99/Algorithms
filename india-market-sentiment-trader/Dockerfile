FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY config ./config
COPY src ./src

RUN pip install --no-cache-dir .

ENV CONFIG_DIR=config
ENV PYTHONUNBUFFERED=1

EXPOSE 8080 9090

CMD ["sentiment-trader"]
