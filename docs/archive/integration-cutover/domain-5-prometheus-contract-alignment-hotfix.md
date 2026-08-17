# Domain 5 Prometheus Contract Alignment Hotfix

## Context

Domain 5 now calls the canonical integration lifecycle guard directly through
`ensure_provider_operational()`. The former local wrapper
`_ensure_instance_operational()` was removed after all Prometheus and
Alertmanager workers migrated to the canonical boundary.

The previous Domain 4 contract required an obsolete inline expression
`if not instance.enabled`. That assertion tested source formatting rather than
the lifecycle behavior and failed after the valid consolidation.

## Contract update

The contract now verifies that:

1. the canonical guard checks provider `enabled` state;
2. the canonical guard checks canonical integration `enabled` state;
3. the canonical guard checks canonical `lifecycle_status` against `active`;
4. Prometheus and Alertmanager validation tasks call the canonical guard before
   `refresh_and_record()`; and
5. no domain-local lifecycle wrapper is reintroduced.

The change removes duplicate indirection without changing the fail-closed
runtime behavior.
