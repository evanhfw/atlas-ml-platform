# syntax=docker/dockerfile:1.7
# Reproducible base: digest is intentionally pinned. Bump it deliberately.
FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# uv is a build tool only; the runtime image does not contain it.
RUN pip install --no-cache-dir uv==0.12.16

# Install runtime dependencies before copying source so this layer is reusable.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
# Install the application as a wheel, not an editable checkout, so the runtime
# image only needs the virtualenv and deployment files.
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV=/app/.venv

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --system --home-dir /app \
       --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=app:app /app/migrations /app/migrations

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"]

# Migrations are deliberately NOT run here. The deployment pipeline runs
# `alembic upgrade head` as a separate, observable step before rolling the app.
CMD ["uvicorn", "atlas_ml_platform.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "30"]
