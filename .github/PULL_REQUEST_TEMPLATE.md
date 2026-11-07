## What changed

<!-- Describe the problem and the smallest useful change. -->

## Why

<!-- Link the issue or explain the user/operator impact. -->

## Validation

- [ ] Relevant API tests and Ruff
- [ ] Relevant web typecheck, lint, tests, and build
- [ ] Node agent tests when applicable
- [ ] OpenAPI client regenerated when the API schema changed
- [ ] Database migration tested on clean and upgrade paths when applicable
- [ ] Desktop and mobile browser flow checked for UI changes
- [ ] `make open-source-check`

Commands and results:

```text

```

## Risk and rollout

<!-- Note migrations, compatibility, security impact, rollback, and operational changes. -->

## External validation boundary

<!-- State which real GPU/provider/vLLM/payment/SMS/production flows were not available. -->

## Documentation

- [ ] Documentation and `CHANGELOG.md` are updated, or this change does not affect users/operators.
- [ ] No secrets, databases, customer data, model weights, or local artifacts are included.
