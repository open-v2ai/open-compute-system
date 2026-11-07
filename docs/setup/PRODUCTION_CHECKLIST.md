# Production readiness checklist

The repository's local demo is not a production deployment. Complete and record every applicable
item before exposing a real environment.

## Required external integrations

- [ ] A real GPU resource provider is implemented and tested for create, query, start, stop,
      release, retry, idempotency, timeout, and error mapping.
- [ ] The Docker/NVIDIA node agent is validated on the target GPU hosts with approved vLLM images.
- [ ] Model licenses and commercial-use rights are reviewed for every deployed model.
- [ ] Token metering and upstream usage are reconciled under success, streaming, timeout, and retry.
- [ ] Production RPM/TPM limits are backed by the intended distributed store and load-tested.
- [ ] SMS/email verification, payment, identity, and legal workflows are implemented if enabled.

## Security

- [ ] Replace all example credentials and generate independent high-entropy secrets.
- [ ] Keep the node agent, Docker socket, vLLM endpoints, metrics, and admin API on private networks.
- [ ] Use HTTPS for public and admin hosts; validate certificate renewal and secure cookies.
- [ ] Restrict admin access, configure real TOTP secrets, and test role permissions server-side.
- [ ] Store provider, model, database, and session secrets in a secret manager.
- [ ] Enable protected branches, required reviews, signed commits/tags where appropriate, secret
      scanning, private vulnerability reporting, Dependabot alerts, and CodeQL.
- [ ] Review container image digests, base-image update policy, SBOMs, and release provenance.

## Reliability and data

- [ ] Run Alembic upgrades against a production-like PostgreSQL snapshot and rehearse rollback.
- [ ] Back up PostgreSQL and Redis where applicable; test restoration and document RPO/RTO.
- [ ] Validate Outbox recovery, worker restarts, task leases, and repeated delivery.
- [ ] Load-test the API, database pool, queue, inference gateway, and provider limits.
- [ ] Configure structured logs, metrics, alerts, dashboards, retention, and on-call ownership.
- [ ] Confirm audit records exclude secrets and contain enough context for incident response.

## Operations and compliance

- [ ] Define data retention, privacy, acceptable-use, incident-response, and abuse-handling policies.
- [ ] Replace demo legal pages with reviewed documents for the operating jurisdiction.
- [ ] Disable demo seed, self-registration until verification exists, and every mock adapter.
- [ ] Verify public routes do not expose supplier cost, internal credentials, or admin-only fields.
- [ ] Record the release version, configuration revision, database migration, image digests, and the
      acceptance evidence for the deployed environment.
