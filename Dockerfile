FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

WORKDIR /app

COPY blinkenlichten/pyproject.toml blinkenlichten/uv.lock ./
RUN uv sync --locked --no-dev

COPY blinkenlichten/*.py blinkenlichten/index.html blinkenlichten/gcdh-logo.svg ./

ENV PORT=55156 \
    WLED_ENDPOINT=http://wled.local

EXPOSE 55156

CMD ["sh", "-c", "exec uv run --no-sync blinkenlichten.py \"$PORT\""]
