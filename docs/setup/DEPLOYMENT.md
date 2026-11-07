# Deployment and shared dependencies

The control plane does not need a GPU. Real vLLM execution belongs on separately validated NVIDIA
hosts; its GPU/VRAM requirements depend on the model and are not included in control-plane sizing.

## Choose a topology

| Mode | Application-owned runtime containers | Dependencies |
| --- | --- | --- |
| Bundled, default | API, Web, Worker, scheduler | Own PostgreSQL, Redis, Nginx |
| External data services | API, Web, Worker, scheduler | Shared PostgreSQL/Redis; own Nginx |
| External data services + host ingress | API, Web, Worker, scheduler | Shared PostgreSQL/Redis and an existing reverse proxy |

There are only **two application image types**. The API, Worker, scheduler and one-shot migration
reuse the same backend image; the frontend uses its own image. Task processes are application-specific
and must not consume another project's queues. Container count and image count are different.

Docker Compose 2.24.4+ is required for the override/reset features. Render and inspect configuration
before starting it; rendered configuration contains credentials, so do not attach it to public issues.

## 1. Bundled dependencies remain the default

```bash
cp deploy/.env.example deploy/.env
# Set independent secrets, real public/admin hosts, TLS paths and production integrations.
python3 deploy/compose.py config --quiet
make build-all
make start
```

This retains production guardrails: demo seed and mock adapters are disabled, secure browser origins
and real TOTP configuration are required. New production users/admins and real resources require an
operator-controlled initialization process; this guide does not claim those external steps are complete.

## 2. Use independently managed shared data services

The default bundled deployment is complete and does not require another repository. To reuse an
existing PostgreSQL/Redis stack, its operator provisions a dedicated database/role, a Redis ACL user,
and a shared Docker network independently of this application. Any compatible operator-managed
stack can be used; no private repository is required.

Keep database/cache containers on the selected network without publishing their ports to the
Internet. Grant the application a non-superuser PostgreSQL role limited to its database and a Redis
user limited to its own key/channel namespace. Use a no-eviction policy for a Redis instance that
carries task queues. Set these application-specific values in the private `deploy/.env`, retaining
its other application settings:

```dotenv
DATABASE_URL=postgresql+asyncpg://ocs_app:replace-with-project-secret@shared-postgres:5432/ocs_app
REDIS_URL=redis://ocs_app:replace-with-project-secret@shared-redis:6379/0
REDIS_KEY_PREFIX=ocs_app
CELERY_QUEUE=ocs_app
SHARED_NETWORK=v2ai-infra
```

The network and DNS names must match the actual shared stack. Never give the application the
infrastructure administrator's credentials. Redis key prefixes are also used for broker, result
and Pub/Sub state. With Redis 7 ACLs, Celery's default `PSUBSCRIBE` patterns need explicit literal
permissions in addition to `&ocs_app:*`: `&ocs_app:broker:/0.celery.pidbox` and
`&ocs_app:broker:/0.celeryev/worker.*` for logical database 0. Adjust those patterns if you change
the database number or Celery exchanges. Do not grant global key/channel access just to make a
connection work. Application users should not have access to flush/admin commands.

```bash
make build-all DEPENDENCIES=external
make start DEPENDENCIES=external
make stop DEPENDENCIES=external
```

External mode starts no application-owned PostgreSQL or Redis. Its `down` does not delete or stop
the independent shared stack. Migrations still execute before the API starts, against the configured
application database only. Connection/authentication failures stop startup rather than falling back
to SQLite or a mock database.

When using existing containers, provide their full connection URLs, scoped
accounts and project prefixes; connect them to the chosen external Docker network. Do not rename,
restart or adopt another project's containers automatically. Redis database numbers alone are not
isolation: configure ACL key/channel rules as well.

## 3. Reuse an existing reverse proxy

```bash
make start DEPENDENCIES=external INGRESS=host
```

This disables the stack's Nginx and exposes Web only on `127.0.0.1:${APP_HTTP_PORT:-18081}`.
Keep `PUBLIC_HOST` and `ADMIN_HOST` as their actual HTTPS domains. Configure the existing proxy to
pass `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`, preserve streaming/timeouts, and keep `/admin`
and `/api/v1/admin` inaccessible on the public user domain. TLS termination, admin access restrictions
and rate limiting remain required. No existing site is changed by the deployment selector.

## 4. Private HTTP preview on a server

For operator-only review, there is an explicit demo overlay. It leaves production validation intact
and makes HTTP, demo seed and fixed development MFA available only in this separately selected mode.
The listener remains on loopback. Do not publish or reverse proxy this demo to the Internet.

In a private `deploy/.env`, set a random `SESSION_SECRET`, the generated project connection settings,
`API_IMAGE` / `WEB_IMAGE` tags if using prebuilt images, `WORKER_CONCURRENCY=1`, and:

```dotenv
PREVIEW_ORIGIN=http://127.0.0.1:3003
APP_HTTP_PORT=18081
```

```bash
python3 deploy/compose.py --dependencies external --preview config --quiet
python3 deploy/compose.py --dependencies external --preview up -d --no-build --wait
```

From the operator's computer:

```bash
ssh -N -L 127.0.0.1:3003:127.0.0.1:18081 your-host-alias
```

Open `http://127.0.0.1:3003`. The frontend is a production build, so demo form autofill may be absent;
use the public demo credentials from the README manually. This is a remote Mock preview, not a
production launch or real GPU delivery.

## 5. Small, private demo without resident task processes

For a handful of visitors per day, select `--demo-lite`. It implies the private `--preview` overlay,
keeps the same PostgreSQL database and accounts, and uses the existing API in-process Mock Outbox
dispatcher. Worker and scheduler containers are disabled, so there is no constant two-second queue
polling. Only API and Web remain as application runtime containers. Shared dependencies remain
separately managed and are not stopped.

When switching an already running full preview, first allow active instance tasks to finish and
stop only that application's background processes:

```bash
python3 deploy/compose.py --dependencies external --preview stop scheduler worker
python3 deploy/compose.py --dependencies external --demo-lite up -d --no-build --wait
```

API and Web each have a 192 MiB limit by default in this mode, configurable using
`DEMO_API_MEMORY_LIMIT` / `DEMO_WEB_MEMORY_LIMIT`. This is an upper bound, not reserved or consumed
memory. The API uses a lightweight 60-second health probe rather than repeatedly importing settings
for a 10-second check. No image rebuild or data migration to SQLite is needed.

This mode is for Mock demonstrations. It pauses Celery scheduling and periodic lease recovery;
API restarts can interrupt in-process work. Keep the full Worker/scheduler topology for durable
background processing or real workloads. Existing production and default bundled settings are not
changed by adding this opt-in mode. To return to the full preview:

```bash
python3 deploy/compose.py --dependencies external --preview up -d --no-build --wait
```

## Public HTTPS Mock sandbox under a subpath

The hosted example is [demo.v2ai.org/open-compute-system](https://demo.v2ai.org/open-compute-system).
It uses the two-container lightweight topology and a shared demo account; visitors must not enter
personal data or real API keys. The operational admin UI/API, registration and login-identity changes
are disabled. Startup refuses real GPU providers or non-Mock inference backends. These restrictions
are server-enforced, not merely hidden navigation.

Provision a **separate public demo database/role** through your infrastructure operator, for example
using the name `open_compute_demo`, and use its dedicated connection settings. Do not
publish existing private preview conversations or records. This creates a new sandbox without
resetting the private database.

For this opt-in deployment set `DEMO_ORIGIN=https://demo.v2ai.org`, `DEMO_HOST=demo.v2ai.org`,
`PUBLIC_BASE_PATH=/open-compute-system`, `PUBLIC_DEMO_PORT=18173`, and a new random session secret
in the private environment file. The public overlay forces HTTPS cookies scoped to the path and
matching frontend CSRF-cookie configuration. Use the host Nginx examples in
`deploy/nginx/public-demo.conf.example` and `deploy/nginx/public-demo-proxy.conf`, with a valid
certificate for your domain and a renewal reload hook. Preserve the prefix when proxying to Web.
The example includes path-specific request limits and body-size limits for this small demonstration.
The proxy snippet also appends `Cache-Control: no-transform` while retaining upstream cache policy.
This prevents CDN HTML transformations such as Cloudflare email obfuscation from changing React's
server-rendered text before hydration; the nonce-based CSP remains intact.

```bash
python3 deploy/compose.py --dependencies external --public-demo config --quiet
python3 deploy/compose.py --dependencies external --public-demo build api web
python3 deploy/compose.py --dependencies external --public-demo up -d --no-build --wait
```

`NEXT_PUBLIC_BASE_PATH`, `NEXT_PUBLIC_PUBLIC_DEMO`, `NEXT_PUBLIC_DEMO_ORIGIN` and
`NEXT_PUBLIC_CSRF_COOKIE` are image build arguments. Rebuild Web when changing these values. Ordinary
root deployments keep their defaults. Next.js handles framework navigation/static assets under its
[basePath](https://nextjs.org/docs/app/api-reference/config/next-config-js/basePath); raw API fetches,
examples, icon URLs, preference cookies and post-login return paths use the same application prefix.

On the hosted sandbox use `demo@opencompute.local` / `Demo12345`. Operations/admin features remain
available when self-hosting the ordinary local demo, not on this shared public sandbox. Keep the
private preview route unpublished; do not point a public proxy at the plain `--preview` mode.

## Queue compatibility and persistence

Existing deployments without namespace variables retain the legacy `celery` queue and unprefixed
Redis keys. New shared projects must set a nonempty prefix and queue. Before switching an existing
live deployment to a new namespace, stop new writes, drain and verify old tasks, then switch every
API/Worker/scheduler together. Do not change only the Worker or flush the old Redis database.

Redis broker, result and Pub/Sub state are namespaced; results expire after one hour. Database
credentials and ACL users survive shared-container restarts. Keep private environment files, infrastructure credential records and named
volumes together with tested backups. No command here intentionally removes data volumes.

The PostgreSQL migration environment normalizes the unnamed legacy orders uniqueness constraint
before the historical hardening revision runs. It preserves data/uniqueness, does not rewrite old
migration files and does not change the final schema or migration head. Worker tasks dispose their
async database pool before closing each task event loop, avoiding asyncpg connections crossing loops.

The preview uses separate session/CSRF cookie names. The matching CSRF cookie name is embedded into
the Web image via `NEXT_PUBLIC_CSRF_COOKIE`; rebuild the Web image when changing `CSRF_COOKIE`.

## Resource sizing and validation

A conservative low-traffic starting point for the full Worker/scheduler topology is **2 vCPU / 2 GiB RAM / 10 GiB free
application disk**, using prebuilt images and Worker concurrency 1. Prefer **4 GiB RAM or more** for
headroom and builds; concurrency, retained data and other projects can require more. These are sizing
recommendations, not a proven production minimum or throughput guarantee.

For the private `--demo-lite` topology, a 2026-11-07 observation on the existing shared AWS host
measured **152–158 MiB** for API + Web, or **188–195 MiB** including the shared PostgreSQL/Redis
containers, over 65 seconds including browser requests. Average application CPU was **1.73% of one
core** in that window. The application memory ceiling is 384 MiB combined; a ceiling is not allocated
memory. These measurements exclude the OS, Docker daemon, other projects and model/GPU execution,
and do not establish the minimum size of a standalone VM. A handful of demo visitors does not need
a dedicated 2 GiB allocation on the already running shared host.

Runtime limits are configurable using `API_MEMORY_LIMIT`, `WEB_MEMORY_LIMIT`, `WORKER_MEMORY_LIMIT`,
`SCHEDULER_MEMORY_LIMIT` and the corresponding `*_CPUS` variables. Shared services have independent
limits. Limits are ceilings, not reservations; measure both cgroup memory and host available memory.
The Web build limits its worker count to two; `NODE_BUILD_MEMORY_MB` controls its Node heap during
image construction only. Prefer CI/prebuilt images; build memory is additional to runtime memory.

```bash
python3 scripts/check_deployment.py
make check-api
make test-api
```

Also verify real PostgreSQL migration, Redis ACL and cross-prefix denial, queue delivery, repeated
lifecycle tasks, browser login and API/worker recovery. Record measured container memory, workload,
image versions and remaining external acceptance in a dated report. Neither a health check nor a
short low-concurrency test establishes production capacity.

References: [Compose merge/override](https://docs.docker.com/reference/compose-file/merge/),
[Compose profiles](https://docs.docker.com/compose/how-tos/profiles/),
[Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/).
