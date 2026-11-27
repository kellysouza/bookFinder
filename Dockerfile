FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app app
COPY db db
ENV PORT=8080
CMD uv run fastapi run app/main.py --host 0.0.0.0 --port ${PORT}
