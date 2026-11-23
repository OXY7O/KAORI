# KAORI Compute Host Asset Registration — Schema Foundation v1

**Authority:** #712 cross-domain Asset Identity, #556 Infrastructure Automation, #4796 and #5155 inventory intent; bounded implementation #5161.

## Owner and boundary

A registered existing Linux host is a **provider-neutral KAORI Compute Host asset**; it is not a Kubernetes `NodeInventory` (which is observed from Kubernetes API after cluster exists), a Git-owned Ansible inventory item, a secret, or an approved execution target.

`ComputeHostAsset` is a minimal non-production source-of-record for stable asset key, display name, site/failure-domain scope, environment, private management IPv4, SSH port and registering actor. It owns no credentials, host-key material or live readiness facts. Existing `IntegrationBinding` shall connect `asset_type=compute_host` and this canonical asset's ID to Ansible; do not add a parallel Ansible-only host association table.

A site/environment/address uniqueness constraint rejects duplicate endpoints **within a site** without wrongly treating overlapping RFC1918 address spaces in different sites as identical. Stable asset_key is globally unique. Endpoints, names and sites remain sensitive scoped asset information and must not be exposed to users lacking approved inventory scope.

## Admission and lifecycle

`app/infrastructure_automation/host_registry_policy.py` validates only the **shape** of a candidate existing host record. It does not authorize mutation or establish SSH trust. There is deliberately no public create/edit/delete route and no secret-key field until the separately gated #5162 RBAC/CSRF/credential-reference and worker trust integration is accepted. The migration creates no rows and activates no automation worker.

The `compute_host_assets` table uses existing application DB/migration ownership. A future authorized registration must persist through canonical audit, enforce owner/tenant scope, identity collision/rename/decommission handling, and link exact `IntegrationBinding` records. An authorized subsequent review snapshot from #5155 includes only redacted fingerprint and counts, not endpoints or credential refs.

## Dependencies and acceptance

- #5162 — credential references, host-key trust, operator permissions, registration/validation UI, real read-only host verification.
- #5163 — authorized inventory projection into immutable review-only Plan JobExecution; stale generation rejection, independent SSH/source/EE authority.
- #5157 — Infrastructure Automation workspace for read-only asset, profile and cluster correlation.
- #4801 — separately approved non-production Kubernetes provisioning, maker/checker, window, isolated Ansible Runner and independent Kubernetes API read-back.

Focused tests: `tests/integrations/test_compute_host_asset_registry_5161.py`; exact-head Ruff/format, Pyright, Alembic schema/migration tests, Developer Check/Full Admission and reviewer. Hosted DB migration/backup/restore and operator UAT are mandatory before any release. Do not confuse schema presence with operational readiness.
