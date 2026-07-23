# KAORI Quality and Architecture Gates

## Purpose

KAORI uses mandatory quality gates to stop architecture debt, migration drift, generated artifacts, and broken frontend assets before a production image can be published.

The canonical local entrypoint is:

```bash
bash scripts/quality_gate.sh --all
```

The release workflow calls the same gates through `.github/workflows/quality.yml`. A tagged production image cannot be published until every quality job succeeds.

## Gate Structure

### Static and Architecture Gate

```bash
bash scripts/quality_gate.sh --static
```

This gate performs:

1. Python bytecode compilation for application, migrations, tests, and scripts.
2. Strict Ruff linting across application, migration, test, and script source.
3. Python dependency-boundary validation.
4. Alembic revision-graph validation without requiring a database.
5. Git tracked-source hygiene validation.
6. Architecture contract tests.
7. Migration contract tests.

### Functional Gate

```bash
bash scripts/quality_gate.sh --tests
```

This runs all permanent tests except the temporary `debug` category. CI provides PostgreSQL and Redis so integration behavior does not silently fall back to an unsupported local environment.

Critical domain characterization suites are also invoked by explicit path after the broad test run. This prevents external marker configuration or `PYTEST_ADDOPTS` from silently deselecting behavior-preservation tests. Analytics Alerts currently uses `tests/analytics/test_alerts_characterization.py` as an explicit release gate.

### Frontend Gate

```bash
bash scripts/quality_gate.sh --frontend
```

This performs a clean `npm ci`, rebuilds local runtime assets and Tailwind CSS, and verifies the generated asset manifest. Runtime CDN dependencies remain prohibited.

### Production Image Gate

CI builds the `production` Docker target only after static, functional, and frontend gates succeed.


## Ruff Zero-Debt Policy

KAORI no longer uses a Ruff diagnostic baseline. The temporary rollout ledger was removed after the post-Batch-2 cleanup reached zero configured diagnostics.

The canonical check is:

```bash
python -m ruff check app migrations tests scripts
```

Rules:

1. Every configured Ruff diagnostic blocks the static gate.
2. New files and changed files receive the same enforcement as existing source.
3. Unused imports must be removed rather than retained as compatibility hints.
4. Import blocks must remain deterministic and grouped by standard library, third-party, first-party, and local imports.
5. Historical Alembic revisions retain narrow per-file exemptions for import-order and annotation-modernization rules only; correctness diagnostics remain mandatory.
6. Ruff suppression comments require a specific rule code and a documented operational reason.

## Architecture Debt Baseline

The machine-readable debt ledger is:

```text
docs/architecture/architecture-debt-baseline.json
```

It does not grant permission to add more debt. It records only known temporary exceptions:

- existing top-level package cycle envelopes;
- existing service-to-WTForms dependencies.

Rules:

1. A cycle may shrink or disappear.
2. No new domain may join an existing cycle envelope.
3. No new service-to-form import may be added.
4. When a listed dependency is removed, its baseline entry must be removed in the same commit.
5. Every baseline entry requires an exit plan.

## Canonical Dependency Direction

New code should follow:

```text
HTTP / CLI / Celery Adapter
        ↓
Application Use Case
        ↓
Domain Contract
        ↓
Provider or Repository Adapter
```

The following are enforced:

- models cannot depend on Flask request globals, routes, or forms;
- task modules cannot import routes or forms;
- service modules cannot import routes;
- wildcard imports are prohibited;
- retired compatibility and empty placeholder files cannot return;
- imports targeting retired Python compatibility modules are rejected even after the files are deleted;
- route modules may only be imported by application/package bootstrap modules.

## Migration Governance

`scripts/verify_migration_graph.py` validates:

- revision IDs are unique;
- every parent revision exists;
- revisions cannot reference themselves;
- the graph has exactly one root;
- the graph has exactly one head;
- the graph contains no cycle.

This static gate complements, but does not replace, database upgrade tests.

## Source Archive Policy

Do not ZIP a working directory. Use:

```bash
bash scripts/build_source_archive.sh
```

The script requires:

- a Git checkout;
- a clean working tree;
- tracked-source hygiene to pass.

It creates the archive with `git archive`, ensuring cache, runtime data, local secrets, and untracked generated files are not distributed.

## Development Completion Checklist

Every logical change must finish with:

```text
code
→ permanent tests
→ relevant documentation
→ quality gate
→ git diff review
→ dedicated Git commit
```
