# Domain 2 — Runtime History Pagination Hardening

## Problem

`paginate_runtime_history()` requested `per_page + 1` observations even though `has_next`
was already calculated from the total row count. A page configured for five observations
could therefore render six rows while its footer still reported a five-row window.

## Decision

Runtime history now uses the canonical pagination contract in `app/common/pagination.py`.
The query requests exactly `PaginationWindow.per_page` rows and uses its normalized offset,
page, boundaries, and navigation metadata.

## Behavior

- Approved page sizes remain 5, 10, 25, and 50.
- Invalid page sizes fall back to 5.
- Out-of-range page numbers clamp to the last available page.
- Empty histories remain zero-safe.
- Prometheus, Alertmanager, and the shared Integrations runtime views receive identical behavior.

## Validation

Run:

```bash
pytest -q \
  tests/integrations/test_runtime_history_pagination.py \
  tests/contracts/integrations/test_runtime_pagination_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert the source, functional test, contract test, and this document in the same commit.
No schema or migration rollback is required.
