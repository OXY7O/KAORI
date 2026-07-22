# KAORI test taxonomy

KAORI separates test evidence by purpose so domain behavior is not confused with migration, cleanup, UI, or diagnostic checks.

| Location | Marker | Purpose | Release evidence |
| --- | --- | --- | --- |
| `tests/<domain>/` | `functional` | Permanent behavior tests for domain functions and failure modes | Yes |
| `tests/contracts/` | `contract` | Dependency direction, ownership, canonical paths, and retired boundaries | Supporting only |
| `tests/migrations/` | `migration` | Alembic upgrade/downgrade, data backfill, and migration graph behavior | Separate gate |
| `tests/debug/` | `debug` | Temporary reproduction and diagnostics | No |

A fixed defect must end with a permanent functional regression test in the owning domain. Debug tests should then be deleted. UI tests may supplement a domain gate but must never be the only evidence for business or security behavior.

Primary commands:

```bash
pytest -q tests/auth -m functional
pytest -q tests/contracts -m contract
pytest -q tests/migrations -m migration
pytest -q -m "not debug"
```
