# Security policy

Open Compute System manages credentials, billing state, GPU workloads, and a Docker-based node
agent. Treat every deployment as security-sensitive.

## Supported versions

| Version | Security updates |
| --- | --- |
| `main` | Yes |
| Latest tagged release | Yes |
| Older releases | Best effort |

Until the project reaches `1.0.0`, security fixes may include breaking changes.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability
reporting feature on the repository's **Security** tab. Include:

- affected version or commit;
- impact and realistic attack scenario;
- reproduction steps or a minimal proof of concept;
- any known mitigation.

Maintainers will acknowledge a complete report within 5 business days and will coordinate a fix,
advisory, and disclosure timeline according to severity. Please do not access data or systems that
you do not own while researching a report.

## Deployment boundary

The default local setup uses demo credentials, SQLite, MockProvider, and MockInferenceBackend. It is
not production-safe. Before production use, follow
[`docs/setup/PRODUCTION_CHECKLIST.md`](docs/setup/PRODUCTION_CHECKLIST.md), replace every example
secret, keep the node agent private, and validate the real GPU provider and inference runtime.
