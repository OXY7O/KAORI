# Domain 2 — Integration Delete Guard Target Identity

## Purpose

KAORI must not delete an integration source while an active canonical job still targets that source. Canonical jobs identify their target through provider columns, scope columns, and a resource-group admission key. The delete guard must recognize all canonical target identities rather than trusting only one representation.

## Behavior

Provider deletion now blocks when an active job matches either:

- `provider_type` and `provider_instance_id`; or
- `resource_group=integration:<provider>:<instance_id>`.

Kubernetes deletion now additionally blocks when an active job matches:

- `resource_group=kubernetes-cluster:<cluster_id>`; or
- `resource_group=integration:kubernetes:<connection_id>`.

Only statuses listed in `ACTIVE_JOB_STATUSES` block deletion. Historical terminal jobs remain retained and do not prevent cleanup.

## Deployment

No database migration is required. Apply the source and test files, run the focused tests, then run the complete integration and quality gates.

## Validation

```bash
pytest -q \
  tests/integrations/test_deletion_guard_target_identity.py \
  tests/contracts/integrations/test_deletion_guard_target_identity_contract.py

pytest -q tests/integrations tests/contracts/integrations
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert the commit. No schema or persisted data rollback is required.

## Changed files

- `app/integrations/deletion.py`
- `tests/integrations/test_deletion_guard_target_identity.py`
- `tests/contracts/integrations/test_deletion_guard_target_identity_contract.py`
- `docs/architecture/domain-2-integration-delete-guard-target-identity.md`
