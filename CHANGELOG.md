# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Public Mock sandbox at `https://demo.v2ai.org/open-compute-system`, with scoped HTTPS cookies,
  subpath-aware navigation/API requests, and disabled operational admin/identity changes.
- Optional shared PostgreSQL/Redis deployment, existing-proxy ingress, and a lightweight two-container
  demo mode; the bundled deployment remains the default.
- Community health files, GitHub issue forms, pull request template, CI, CodeQL, and Dependabot.
- Bilingual project entry points and an explicit production-readiness checklist.
- Repository hygiene checks for accidentally tracked secrets, databases, caches, and build output.
- Self-hosted GPU instance control-plane MVP with SKU, inventory, orders, tasks, and lifecycle APIs.
- OpenAI-compatible model API, API keys, token metering, billing, and an auto-router prototype.
- FastAPI control plane, Next.js user/admin web apps, Celery workers, and a controlled Docker vLLM
  node agent.
- Local SQLite and mock runtime for development and acceptance testing.

[Unreleased]: https://github.com/open-v2ai/open-compute-system/commits/main
