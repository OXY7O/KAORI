# KAORI Test Taxonomy

KAORI separates evidence by purpose so behavior tests are not confused with migration, cleanup, architecture, UI, or temporary diagnostic checks.

| Location | Marker | Purpose | Release evidence |
| --- | --- | --- | --- |
| `tests/<domain>/` | `functional` | Permanent domain behavior, failure modes, security controls, and operational outcomes | Primary |
| `tests/contracts/` | `contract` | Dependency direction, ownership, canonical paths, and retired boundaries | Supporting |
| `tests/migrations/` | `migration` | Alembic upgrade/downgrade, data backfill, and migration graph behavior | Separate gate |
| `tests/debug/` | `debug` | Temporary reproduction and diagnostics | Excluded |

`tests/conftest.py` is the only marker-assignment hook. It assigns markers from the first directory below `tests/`. Nested marker hooks are prohibited because they can silently change release selection.

A fixed defect must end with a permanent functional regression test in the owning domain. A debug test should then be removed or rewritten as that permanent test. UI or source-contract tests may supplement behavior evidence, but must never be the only validation for business, security, persistence, or worker logic.

Final-reviewed core domains have an explicit characterization gate; Welcome is included alongside the existing Inventory and Analytics foundations:

```bash
python scripts/verify_feature_test_coverage.py
pytest -q tests/welcome tests/analytics tests/inventory tests/kubernetes -m functional
```

Primary commands:

```bash
pytest -q tests/auth -m functional
pytest -q tests/contracts -m contract
pytest -q tests/migrations -m migration
pytest -q tests/debug -m debug
pytest -q -m 'not debug'
```
