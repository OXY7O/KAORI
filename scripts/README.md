# KAORI Application Scripts

The top-level `scripts/` directory is reserved for KAORI application lifecycle, application validation, database/bootstrap, frontend build support, and application release verification.

Use other ownership boundaries for non-application tooling:

- `example/` — standalone demo/integration bootstrap stacks and disposable helpers.
- `deploy/` — staging/production Host deployment tooling.
- `.github/` — GitHub Actions workflow and runner/CI orchestration authority.

Do not add provider demo bootstrap, disposable runner bootstrap, private Host administration, or environment-specific operational scripts under `scripts/`.

Scripts that validate KAORI source/runtime contracts remain application-owned when they are part of the product release/admission boundary. Their operator output should follow [`docs/engineering/TERMINAL_OUTPUT.md`](../docs/engineering/TERMINAL_OUTPUT.md).
