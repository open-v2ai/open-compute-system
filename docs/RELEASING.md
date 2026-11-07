# Release process

Open Compute System follows Semantic Versioning. Before `1.0.0`, minor releases may contain breaking
changes, which must be called out in the changelog and release notes.

## Release gates

1. Confirm the release scope and move user-facing entries from `Unreleased` in `CHANGELOG.md`.
2. Run `make check`, `make test`, `make build`, and `make open-source-check` from a clean checkout.
3. Regenerate the OpenAPI contract and confirm there is no unexpected diff.
4. Upgrade a clean database to Alembic head; for migrations, also test an upgrade from the previous
   release.
5. Review dependencies, CodeQL findings, secret scanning, and open security advisories.
6. Verify example configuration contains no real credentials or customer-specific values.
7. Document which real GPU, inference, Docker/NVIDIA, and production flows were actually exercised.

## Publish

1. Update project versions consistently in the API, node agent, web package, and FastAPI metadata.
2. Tag the reviewed commit as `vMAJOR.MINOR.PATCH` using a signed tag.
3. Build release artifacts only in CI from the tag.
4. Publish checksums and provenance for downloadable artifacts.
5. Create GitHub release notes from `CHANGELOG.md`; enable immutable releases when available.

Publishing a Git tag or container is a maintainer action and is never implied by a successful build.
Production deployment is a separate, explicitly authorized operation.
