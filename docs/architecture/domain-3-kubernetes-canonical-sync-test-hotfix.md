# Domain 3 Kubernetes Canonical Sync Test Hotfix

## Problem

The functional test attempted to monkeypatch `Cluster.query` directly. In Flask-SQLAlchemy, `query` is a descriptor that resolves the scoped session and therefore requires an active Flask application context even before monkeypatch can replace it.

## Resolution

The test now replaces the module-level `Cluster` symbol in `app.kubernetes.cluster.sync_jobs` with a lightweight model stub exposing the expected query chain. This keeps the test focused on admission behavior and avoids coupling the unit test to Flask application-context setup.

## Production impact

None. Production source is unchanged.

## Validation

```bash
pytest -q \
  tests/kubernetes/test_inventory_sync_canonical_resolution.py \
  tests/contracts/kubernetes/test_inventory_sync_canonical_resolution_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Restore the previous version of `tests/kubernetes/test_inventory_sync_canonical_resolution.py`.
