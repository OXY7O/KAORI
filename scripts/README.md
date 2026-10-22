# KAORI Application Scripts

The top-level `scripts/` directory is reserved for KAORI application lifecycle, application validation, database/bootstrap, frontend build support, and application release verification.

Use other ownership boundaries for non-application tooling:

- `example/` — standalone demo/integration bootstrap stacks and disposable helpers.
- `deploy/` — staging/production Host deployment tooling.
- `.github/` — GitHub Actions workflow and runner/CI orchestration authority.

Do not add provider demo bootstrap, disposable runner bootstrap, private Host administration, or environment-specific operational scripts under `scripts/`.

Scripts that validate KAORI source/runtime contracts remain application-owned when they are part of the product release/admission boundary. Their operator output should follow [`docs/engineering/TERMINAL_OUTPUT.md`](../docs/engineering/TERMINAL_OUTPUT.md).


## Existing DevContainer PostgreSQL schema upgrade (operator only)

**Do not run** `flask db upgrade` using the runtime Flask `DATABASE_URL`.
Only the one-shot `db-bootstrap` Compose service can use the dedicated
`kaori_migrator` credential, then refresh grants for `kaori_runtime`.
The guarded, explicit **existing DB** upgrade command from the repository root:

```sh
python scripts/verify_migration_graph.py
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml \
  run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

**Important:** `run --rm db-bootstrap --upgrade-only` is incorrect:
Compose replaces the service command with the bare flag, so the image
entrypoint executes `--upgrade-only` as a program and fails before Alembic.
Providing the full script command is required for an existing database.
DevContainer `db-first-run` is virgin-schema only; it will not auto-upgrade
an existing or partially migrated database.

The guarded script validates APP_ENV, separate migration credential and
non-superuser database ownership, calls `scripts/init_db.sh --schema-only`,
refreshes runtime role grants and seeds RBAC without creating a fresh admin
for `--upgrade-only`. Never use `flask db stamp`, edit `alembic_version`,
drop tables or reset the PostgreSQL volume to bypass a migration error.
From the running DevContainer terminal use
`flask --app run:app db current` and inspect the new head after
successful upgrade. If a different environment already applied a renamed
review-only revision, stop and reconcile migration evidence first; this
correction assumes the reported DevContainer is at
`20261013_limit_exposure`.
