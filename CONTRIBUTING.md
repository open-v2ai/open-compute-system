# Contributing to Open Compute System

Thanks for helping improve Open Compute System. Small, focused pull requests with tests and a clear
problem statement are the easiest to review.

## Before you start

- Search existing issues and pull requests.
- Use a discussion or feature request before investing in a large behavior or architecture change.
- Never include customer data, credentials, model weights, database files, or generated local
  artifacts.
- Read the current product boundary in [`README.md`](README.md) and
  [`docs/business/PRODUCT_PRD.md`](docs/business/PRODUCT_PRD.md). Historical PRDs are not the
  implementation roadmap.

## Development setup

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22, pnpm 11.20, and Docker
when testing PostgreSQL, Redis, or the node agent.

```bash
cd api
uv sync --frozen
uv run python scripts/upgrade_database.py

cd ../web
pnpm install --frozen-lockfile
```

Run the API and web app in separate terminals:

```bash
make dev-api
make dev-web
```

The local environment uses SQLite and mock adapters. See
[`docs/setup/MVP_ACCEPTANCE.md`](docs/setup/MVP_ACCEPTANCE.md) for what that does and does not prove.

## Architecture rules

- Keep backend calls flowing through `routers -> services -> repositories/models/providers`.
- Put authorization, business rules, transactions, idempotency, and state machines in services.
- Keep the order, inventory reservation, task, and Outbox event in one consistency boundary.
- Treat FastAPI OpenAPI as the only frontend API contract. Do not hand-edit files under
  `web/lib/api/generated/`; run `make generate-client` after backend schema changes.
- Reuse the existing shadcn/ui primitives and Lucide icons in the web app.
- Do not turn a mock success into a claim about real GPU delivery or production readiness.

## Validation

Run the smallest relevant checks while developing and the full suite before opening a pull request:

```bash
make check
make test
make build
make open-source-check
```

Database changes also require an Alembic migration and an empty-database upgrade check:

```bash
cd api
DATABASE_URL=sqlite+aiosqlite:////tmp/open-compute-system-empty.db \
  .venv/bin/alembic upgrade head
```

UI changes should be exercised in a real browser at desktop and mobile widths. State clearly when a
real provider, Docker/NVIDIA node, authentication provider, payment system, or production deployment
was not available for verification.

## Pull requests

- Keep unrelated cleanup out of the change.
- Use an imperative, descriptive title; Conventional Commit prefixes are welcome but not required.
- Add or update tests for behavior changes.
- Update documentation and `CHANGELOG.md` when users or operators are affected.
- Explain migrations, compatibility impact, security impact, and external validation boundaries.
- Confirm that generated OpenAPI artifacts are current and CI is green.

By submitting a contribution, you agree that it is licensed under the Apache License 2.0.
