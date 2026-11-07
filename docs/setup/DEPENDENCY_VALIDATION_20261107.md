# Dependency integration and AWS validation

Date: 2026-11-07 (Asia/Shanghai).

## Integrated changes

The combined update covers Dependabot PRs #2–#8 and #10, and supersedes the lower Next.js security
target in #11. It uses Next.js 16.4.5, React 19.3.1, TypeScript 6.0.3, Recharts 3.10.1, FastAPI
0.162.0 and Redis client 8.1.0. Kombu 5.7.0 and AMQP 5.4.2 were resolved together with Redis.

PR #1's Node.js 25 target was not adopted because it is EOL. Node.js stays on 22 LTS, and Node.js
types move from 20 to 22 instead of PR #9's 26 target. Dependabot ignores automatic major updates
for these runtime pins. See the [Node.js release status](https://nodejs.org/en/about/previous-releases).

## Checks executed on AWS

All application checks and builds ran on the existing AWS host. The operator's computer prepared
source/lockfiles and ran browser clients against AWS; it did not run a local application deployment.

| Check | Result |
| --- | --- |
| API Ruff and pytest, Python 3.13.18, dedicated PostgreSQL database | 68 passed |
| Node agent Ruff and pytest with its locked dependencies | 6 passed |
| Web TypeScript, ESLint and Vitest | 15 passed |
| Next.js standalone Docker builds, private preview and public subpath configuration | Passed |
| Compose topology validation and repository hygiene | Passed |
| OpenAPI generation | Both generated files unchanged |
| Clean PostgreSQL migration and existing public-demo upgrade | Passed; no schema revision change |
| Nginx 1.29 Docker proxy and configuration validation | Passed |

The first API test container inherited preview settings and rejected TestClient's `testserver`
host. The suite was rerun in a fresh database with the normal CI environment. Agent cache paths
were placed in the test container's temporary directory because source mounts were read-only.

## Live deployment acceptance

An isolated AWS Compose project used its own PostgreSQL and Redis containers, API, Web, Celery
worker and scheduler. Through Nginx, acceptance covered user/admin login, hidden supplier-cost
fields, instance creation and idempotent replay, stop/start/release, persisted chat and metering,
API-key completions, SSE and key revocation. All 30 readiness requests at concurrency 5 succeeded;
the observed P95 was 49.81 ms. This short smoke check is not a capacity guarantee.

Desktop and 390 × 844 browser checks passed. The mobile document width equaled the viewport width.
Browser console errors and warnings were zero after the final fixes.

The public HTTPS demo at [demo.v2ai.org/open-compute-system](https://demo.v2ai.org/open-compute-system)
was then updated and rechecked for prefixed assets, homepage CSP, secure path-scoped session/CSRF
cookies, blocked admin/operations routes and identity changes, login/logout, instance lifecycle,
chat and metering. Existing shared demo data was preserved.

Public acceptance exposed Cloudflare email rewriting that changed React's server-rendered text.
The proxy now appends `Cache-Control: no-transform` while preserving upstream cache directives;
the CSP is retained. The subpath root also has an explicit Proxy matcher. See
[Cloudflare's documented behavior](https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/).

## Deployment and rollback

Database dumps, previous environment files and changed source files were backed up before each
public cutover. An initial HTTP probe raced frontend startup and triggered the old-image rollback;
the deployment check then used bounded readiness retries. The final public images are:

- API: `sha256:c628733590b4f5fce3364dbbf176636ad9e38d106dc698ff24dac484790772e6`
- Web: `sha256:a1e6110fef8eb66ed7b2b3046609cce856f5fc8db15a3b018c9330e670aeda96`

The final Web runtime reports Node.js 22.23.4. API and Web retain their existing 192 MiB memory
limits. Temporary test containers, network, SSH tunnel and browser sessions were closed; test
volumes and rollback artifacts were retained. Other applications and shared data services were
not restarted. The existing host Nginx binary was not upgraded; Nginx 1.29 was tested as the bundled
Docker dependency.

## External boundary

PostgreSQL, Redis, Celery, Docker, TLS/CDN ingress and browser flows above were real. GPU resource
delivery and inference replies remained Mock. Real NVIDIA/vLLM execution, model identity and Token
reconciliation, payment, SMS, formal legal terms and production capacity were not accepted by this
validation. The hosted application remains a shared Mock sandbox.
