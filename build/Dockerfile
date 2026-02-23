FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# ставим uv
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

# сначала только метаданные зависимостей (для кеша)
COPY pyproject.toml uv.lock ./

# ставим зависимости строго по lock
RUN uv sync --frozen --no-dev

# затем код
# COPY . .

# user
RUN useradd -m appuser
USER appuser
# code
COPY --chown=appuser:appuser . .


CMD ["uv", "run", "python", "-m", "src.run"]


