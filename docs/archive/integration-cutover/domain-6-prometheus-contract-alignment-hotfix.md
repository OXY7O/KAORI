# Domain 6 Prometheus Contract Alignment Hotfix

## Purpose

Domain 6 moved provider operational checks from the validation worker's local compatibility wrapper into the shared integration lifecycle guard, `ensure_provider_operational()`.

The Domain 4 Prometheus contract still required the old inline implementation and therefore failed even though the production behavior remained enforced through the shared guard.

## Contract update

The updated contract verifies the actual architecture:

- the validation worker delegates to `ensure_provider_operational()`;
- the shared guard rejects a disabled provider record;
- the shared guard rejects a disabled canonical integration;
- the shared guard rejects a canonical lifecycle other than `active`;
- the Prometheus validation branch calls the guard before `refresh_and_record()`.

No production behavior or database schema changes are included.

## Rollback

Restore the previous version of:

`tests/contracts/prometheus/test_domain4_prometheus_runtime_contract.py`
