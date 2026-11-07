# Open-source publication checklist

Repository files are only half of an open-source launch. Complete these GitHub-side actions before
changing visibility or announcing the project.

## Repository identity

- [ ] Confirm the canonical repository is `open-v2ai/open-compute-system`; update README, package
      metadata, badges, and changelog links if the final owner or name differs.
- [ ] Confirm Apache-2.0 matches the intended commercial and patent policy with the copyright owner.
- [ ] Add a concise GitHub description, website if available, and topics such as `gpu`, `vllm`,
      `fastapi`, `nextjs`, `inference`, `self-hosted`, and `openai-compatible`.
- [ ] Add a readable 1280×640 social preview and verify the README in GitHub's renderer.

## Community settings

- [ ] Enable Issues and Discussions; verify issue forms and support links point to the final repo.
- [ ] Enable private vulnerability reporting and use the Security tab as the channel in
      `SECURITY.md`.
- [ ] Nominate at least two maintainers and configure CODEOWNERS once real GitHub users or teams are
      confirmed.
- [ ] Publish a private conduct-reporting contact on the organization profile and verify the wording
      in `CODE_OF_CONDUCT.md`.
- [ ] Define triage labels, a response policy, and a process for stale issues without auto-closing
      valid reports prematurely.

## Branch and automation protection

- [ ] Protect `main`: require pull requests, at least one review, conversation resolution, and the
      CI/repository hygiene checks.
- [ ] Restrict force pushes and branch deletion; define who can bypass protection.
- [ ] Set default GitHub Actions token permissions to read-only and allow write permissions only in
      explicitly reviewed workflows.
- [ ] Enable dependency graph, Dependabot alerts/security updates, secret scanning and push
      protection, and CodeQL.
- [ ] Review every third-party GitHub Action and decide whether organization policy requires full
      commit-SHA pinning.

## Clean-room release check

- [ ] Publish from a fresh clone, not from the current development directory.
- [ ] Confirm `git status --ignored` shows local databases, `.env`, caches, Playwright artifacts,
      `.next`, and `node_modules` as ignored and untracked.
- [ ] Run `make install`, `make check`, `make test`, `make build`, and `make open-source-check`.
- [ ] Inspect `git ls-files` for secrets, databases, certificates, customer data, screenshots, large
      binaries, and copied third-party material.
- [ ] Validate a clean SQLite migration and a production-like PostgreSQL migration.
- [ ] Create a signed `v0.1.0` tag only after the changelog, release notes, and known limitations are
      accurate.

## Launch communication

- [ ] Lead with the actual problem, architecture, quick start, and current limitations.
- [ ] Do not claim production readiness, real GPU delivery, payment, SMS, model licensing, or legal
      readiness without recorded external acceptance.
- [ ] Prepare one reproducible demo path and seed data that contain no private or customer content.
- [ ] Publish a roadmap based on the current product PRD, not the historical parity and quotation
      documents.
