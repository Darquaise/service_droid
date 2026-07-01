FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# install dependencies first for layer caching (only re-runs when the lock changes)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --frozen

COPY backend/ ./

# Alembic owns the schema: apply pending migrations, then start the bot.
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
