# Domain 5 Prometheus Contract Alignment Hotfix

## Context

Domain 5 centralized provider and canonical lifecycle checks in
`_ensure_instance_operational()` so Prometheus and Alertmanager workers share one
fail-closed implementation.

The Domain 4 contract still required the obsolete inline expression
`if not instance.enabled`. That assertion tested source formatting rather than
the lifecycle boundary and failed after the valid refactor.

## Contract update

The contract now verifies that:

1. the centralized helper checks provider `enabled` state;
2. the helper checks canonical integration `enabled` state;
3. the helper checks canonical `lifecycle_status` against `active`; and
4. Prometheus full validation invokes the helper before `refresh_and_record()`.

No production behavior changes are included.
