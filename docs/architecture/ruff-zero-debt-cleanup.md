# Ruff Zero-Debt Cleanup

## Scope

This cleanup closes the temporary lint-debt phase introduced while the foundation and integration ownership gates were being established. It is intentionally behavior-preserving.

## Resolved Diagnostics

The cleanup removed all 260 diagnostics remaining after the TLS runtime fix:

- 170 unused imports (`F401`);
- 79 unsorted or non-canonical import blocks (`I001`);
- 9 standard-library collection imports modernized from `typing` to `collections.abc` (`UP035`);
- 2 unnecessary UTF-8 arguments removed from `str.encode` (`UP012`).

The earlier TLS runtime fix had already removed one `F401` entry from the original 261-diagnostic rollout baseline, leaving the 260 diagnostics resolved here.

## High-Value Cleanup Areas

The largest concentration was in `app/inventory/resources/`, where files retained broad import sets from an earlier service split. Each resource module now imports only the models, formatting functions, and query helpers it actually uses.

Integration, analytics, reporting, Kubernetes operations, jobs, authentication support, models, and quality scripts also received deterministic import normalization.

## Enforcement

The temporary files below are retired:

```text
docs/architecture/ruff-debt-baseline.json
scripts/verify_ruff_baseline.py
tests/contracts/quality/test_ruff_baseline_contract.py
```

The static gate now runs Ruff directly:

```bash
python -m ruff check app migrations tests scripts
```

Historical Alembic revisions retain only narrow style exemptions in `pyproject.toml`. Undefined names, unused imports, syntax problems, and other correctness diagnostics remain enforced.

## Change Policy

Future work must not recreate a lint baseline. When a rule requires a temporary exception, use a narrowly scoped suppression with the exact rule code, an operational reason, an owner, and a removal condition.
