# KAORI Quality and Architecture Gates

## Purpose

KAORI uses mandatory release gates to prevent behavior regressions, import-cycle failures, architecture drift, migration divergence, generated artifacts, and duplicated UI implementation before a production image is published.

The canonical local entrypoint is:

```bash
bash scripts/quality_gate.sh --all
```

The release workflow calls the same gate through `.github/workflows/quality.yml`. A production image must not be published until every phase succeeds.

## Gate Structure

### Static and Architecture Gate

```bash
bash scripts/quality_gate.sh --static
```

This gate performs, in order:

1. Source hygiene validation, including source archives that do not contain `.git` metadata.
2. In-memory Python syntax compilation without generating `__pycache__` or `.pyc` files.
3. Strict Ruff linting.
4. Ruff formatting verification.
5. djLint validation for Jinja templates.
6. Pyright type and import analysis.
7. Architecture dependency-boundary validation.
8. Internal module and imported-symbol resolution.
9. Runtime import-cycle detection, excluding imports guarded by `TYPE_CHECKING`.
10. Application-module reachability validation.
11. Celery task, route, queue, worker, and Beat topology validation.
12. Code-health debt-ceiling validation.
13. Alembic revision-graph validation.
14. Test location and marker-taxonomy validation.
15. Inventory and Analytics characterization-test coverage validation.
16. Jinja syntax, reusable UI boundary, and inline-debt validation.
17. Architecture and migration contract tests.

### Functional Gate

```bash
bash scripts/quality_gate.sh --tests
```

The broad test run executes every permanent test except the temporary `debug` category:

```bash
pytest -q -m 'not debug'
```

Inventory and Analytics foundations are then invoked explicitly:

```bash
pytest -q tests/analytics tests/inventory tests/kubernetes -m functional
```

The explicit invocation prevents environment-level marker configuration or `PYTEST_ADDOPTS` from silently deselecting behavior-preservation suites.

### Frontend Gate

```bash
bash scripts/quality_gate.sh --frontend
```

This performs a clean dependency installation, Prettier verification, local runtime-asset generation, Tailwind CSS compilation, and generated-asset verification:

```bash
npm ci --no-audit --no-fund
npm run check-format
npm run build-frontend
npm run verify-frontend
```

Runtime CDN dependencies remain prohibited.

## Test Taxonomy

One hook in `tests/conftest.py` owns path-based marker assignment:

| Location | Marker | Release role |
| --- | --- | --- |
| `tests/<domain>/` | `functional` | User-visible, operational, security, and failure behavior |
| `tests/contracts/` | `contract` | Architecture ownership and retired boundaries |
| `tests/migrations/` | `migration` | Upgrade, downgrade, data backfill, and graph behavior |
| `tests/debug/` | `debug` | Temporary reproduction only; excluded from release |

Nested `conftest.py` marker hooks are prohibited. A defect may begin with a debug reproduction, but it must finish with a permanent regression test in the owning domain before the debug test is removed.

## Import and Initialization Safety

KAORI validates three separate import properties:

1. Every internal module exists.
2. Every explicitly imported top-level symbol is defined or re-exported by its target module.
3. The runtime import graph is acyclic.

This is designed to detect missing implementation files, stale re-exports, partially initialized modules, and circular imports before pytest collection or application startup.

## Ruff Zero-Debt Policy

KAORI does not use a Ruff diagnostic baseline. The canonical checks are:

```bash
python -m ruff check app migrations tests scripts
python -m ruff format --check app migrations tests scripts
```

Rules:

1. Every configured Ruff diagnostic blocks the static gate.
2. New and existing files receive the same enforcement.
3. Unused imports must be removed rather than retained as compatibility hints.
4. Import blocks must remain deterministic and grouped by standard library, third-party, and first-party imports.
5. Historical Alembic revisions retain only narrow per-file exemptions for import ordering and annotation modernization.
6. Suppression comments require a specific rule code and an operational reason.

## Architecture and Code-Health Debt

The machine-readable ledgers are:

```text
docs/architecture/architecture-debt-baseline.json
docs/architecture/code-health-debt-baseline.json
```

They are ceilings, not quality targets. A listed cycle, form dependency, broad exception, large module, or large function may shrink or disappear, but it may not expand. A resolved entry must be removed from the baseline in the same change.

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

- models cannot depend on request globals, routes, or forms;
- task modules cannot import routes or forms;
- services cannot import routes;
- wildcard imports are prohibited;
- retired compatibility, shim, and empty placeholder modules cannot return;
- imports targeting retired modules remain prohibited after deletion;
- application modules must have an importer, configured runtime entrypoint, test consumer, or script consumer;
- route modules may only be imported by application or package bootstrap modules.

## Reusable UI Boundary

Dynamic progress widths are centralized in:

```text
app/templates/components/progress_bar.html
```

Templates outside that component may not use inline `style=` attributes. `scripts/verify_ui_reuse.py` also parses every Jinja template, rejects local `<style>` blocks, and prevents inline scripts or event handlers from increasing beyond the recorded burn-down baseline.

The remaining inline-script and event-handler baseline records existing debt only. New UI work must prefer shared Jinja components, Alpine behavior, HTMX attributes, and static frontend modules.

## Migration Governance

`scripts/verify_migration_graph.py` validates:

- revision IDs are unique;
- every parent revision exists;
- revisions cannot reference themselves;
- the graph has exactly one root;
- the graph has exactly one head;
- the graph contains no cycle.

This static gate complements database upgrade and downgrade tests; it does not replace them.

## Source Archive Policy

Do not ZIP a working directory. Use:

```bash
bash scripts/build_source_archive.sh
```

The script requires a clean Git checkout and creates the archive with `git archive`. Cache directories, compiled bytecode, local runtime data, secrets, generated reports, and nested ZIP files are rejected. When a source archive is audited without `.git`, the hygiene gate scans the entire archive rather than skipping validation.

## Development Completion Checklist

Every logical change must finish with:

```text
code
→ permanent functional tests
→ relevant contract or migration tests
→ documentation
→ static, functional, and frontend gates
→ git diff review
→ dedicated Git commit
```
