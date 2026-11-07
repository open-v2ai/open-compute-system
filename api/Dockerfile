FROM python:3.13-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /uvx /bin/
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY app ./app
RUN addgroup --system --gid 1001 opencompute \
    && adduser --system --uid 1001 --ingroup opencompute opencompute \
    && chown -R opencompute:opencompute /app
USER opencompute
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
