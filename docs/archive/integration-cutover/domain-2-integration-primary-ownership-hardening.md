# Domain 2 — Integration Primary Ownership Hardening

## Problem

An enabled binding could continue to reserve the `primary` role after its canonical
Prometheus or Alertmanager source was disabled. KAORI then rejected assignment of
a replacement primary even though the existing source was not operationally eligible.

## Decision

Primary-conflict lookup now requires all of the following:

- matching provider type;
- canonical integration source is enabled;
- binding is enabled;
- matching scope and primary role.

Disabling a source therefore releases operational primary ownership without deleting
its binding, validation evidence, runtime history, or audit history.

## Files

- `app/integrations/prometheus/binding_management.py`
- `app/integrations/alertmanager/binding_management.py`
- `tests/integrations/test_primary_binding_eligibility.py`
- `tests/contracts/integrations/test_primary_binding_ownership_contract.py`

## Validation

Run:

```bash
pytest -q tests/integrations/test_primary_binding_eligibility.py
pytest -q tests/contracts/integrations/test_primary_binding_ownership_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert the domain commit. No schema or data migration is involved.
