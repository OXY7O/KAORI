# Vault / Secrets & PKI — Integrated UAT Acceptance Matrix

Authority: HV-09 #2593; architecture #714; resource scope #724; workstreams HV-01–HV-15.
This document is a test protocol, **not** executed evidence or human acceptance.

## Exact-SHA evidence requirements

Record the tested Git SHA, DevContainer/target source version, Vault instance
and approved namespace/scope, known test case, JobExecution ID, Alembic HEAD,
worker readiness, sanitized output, test/CI run URL, security-denied actor and
permission, browser light/dark/responsive result, and named human acceptance.
Use PASS / FAIL / Not Tested / Not Implemented explicitly. Never log, export
or screenshot plaintext Secret values, Vault paths/names where sensitive,
SecretIDs, tokens, private keys, dynamic credentials or value hashes.

## Source / verification status (as of 2026-10-22)

Every source row below is **Not Tested**, not a PASS. Workstreams marked
Not Implemented must not be treated as waived acceptance.

| Workstream | Review source / capability limit | Verification |
| --- | --- | --- |
| HV-01 #2585 | Vault AppRole provider/TLS origin, validation and runtime | Not Tested |
| HV-02 #2586 | KV v2 metadata-only collector, committed JobExecution | Not Tested |
| HV-03 #2587 / #2683 | Opted-in public PKI evidence + qualified aggregate validity windows | Not Tested |
| HV-04 #2588 / #2674 | KV v2 version lifecycle aggregate; rotation contract only | Not Tested |
| HV-05 #2589 / #2666 | Fingerprint/Ingress/UID/ESO reconciliation *candidates* only | Not Tested |
| HV-06 #2590 / #2697 | Metrics/Alert Source bindings; bounded recent-hour Vault query-range qualification | Not Tested |
| HV-07 #2591 / #2678 / #2683 / #2761 | Committed Overview/Inventory, new Lifecycle & Assurance capability navigation/read model, unpublished scoped Registry, PKI validity aggregate; sensitive Detail and other workspaces not implemented | Not Tested |
| HV-08 #2592 | Governed provider operation pilot | Not Implemented |
| HV-09 #2593 | UAT protocol; live scenarios not executed | Not Tested |
| HV-10 #2594 / #2702 | Current-generation public PKI expiration horizon workspace; historical MetricsConsumer datasets/pages absent | Not Tested |
| HV-11 #2595 / #2778 | Review candidate: one population-level qualified PKI public expiry-pressure Intelligence rule; per-asset rules remain unimplemented | Not Tested |
| HV-12 #2596 | Vault-enriched AlertCase investigation | Not Implemented |
| HV-13 #2597 / #2678 | Base permission catalog and fail-closed internal read contract; canonical #724 policy evaluator still absent | Not Tested |
| HV-14 #2598 | Role-aware Welcome entry | Not Tested |
| HV-15 #2599 | Canonical Reports definitions | Not Implemented |

## DevContainer and PostgreSQL

Use the existing approved first-run procedure at
docs/operations/devcontainer-postgres-first-run.md. An existing database never
auto-migrates. Only on an explicitly reviewed *local* target, Windows host
PowerShell may run:

~~~powershell
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml config --quiet
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml exec -T db psql -U postgres -d kaori -X -v ON_ERROR_STOP=1 -c "SELECT version_num FROM public.alembic_version;"
~~~

Do not migrate with the runtime DB user, delete PGDATA, use down --volumes,
stamp Alembic, waive restricted-runtime grants or bypass worker schema gates.
Record the exact SHA before/after checks. Start the canonical web/inventory
workers per the DevContainer procedure; queued jobs are not completed jobs.

## Existing quality and source-focused checks

~~~bash
git rev-parse HEAD
python -m ruff check app/secrets_pki app/integrations/secrets_management tests/integrations
python -m ruff format --check app/secrets_pki app/integrations/secrets_management
python -m pytest -q \
  tests/integrations/test_vault_provider.py \
  tests/integrations/test_vault_kv2_inventory.py \
  tests/integrations/test_vault_kv2_committed_inventory.py \
  tests/integrations/test_vault_kv2_version_posture.py \
  tests/integrations/test_scoped_secrets_pki_registry.py \
  tests/integrations/test_vault_pki_public_evidence.py \
  tests/integrations/test_vault_pki_validity_posture.py \
  tests/integrations/test_vault_metrics_binding.py \
  tests/integrations/test_vault_alert_source_binding.py \
  tests/integrations/test_certificate_delivery_read_model.py \
  tests/kubernetes/governance/test_tls_object_uid_collection.py \
  tests/kubernetes/governance/test_tls_controller_owner_evidence.py \
  tests/kubernetes/governance/test_eso_reconciliation_contract.py \
  tests/contracts/secrets_pki/test_lifecycle_evidence_contract.py
python -m pyright --project pyrightconfig.json
bash scripts/quality_gate.sh --static
~~~

Run existing Developer Check and Full Admission through approved GitHub flow.
The review branch alone does not trigger Developer Check. Report missing
workflow evidence as Not Tested; do not manufacture green status.

## Mandatory source-specific negative acceptance

| Domain | Real source / security evidence to collect |
| --- | --- |
| Vault core | Nonroot AppRole; HTTPS/CA/approved origin; denied scopes; active/standby/sealed/uninitialized/unavailable where safe |
| KV v2 | Known populated and empty approved mounts; no data endpoint; 403/404; partial, failed, stale; version delete/destroy |
| PKI | Issuer and stored cert opt-in, missing/no-store cases, 403, rollover; expired/not-yet-valid/unknown public validity, stale or opt-out counts suppressed; no PEM/private-key persistence |
| Kubernetes | TLS Secret deletion/recreation same name different UID; stale Ingress; controller ownership candidates |
| ESO | Actual supported CRD Ready/refresh/sync-version behavior and separate current TLS UID; never infer Vault delivery |
| Rotation/Lease | Version increment is not verified cutover; elapsed known Lease expiry is not revocation |
| Metrics/Alerts | Prometheus/Thanos label binding, historical retention, HA ambiguity, foreign Alert Source labels denied |
| Scope/RBAC | Internal read contract deny/wrong-actor/expired-grant tests; canonical persisted #724 scope evaluator not implemented; prohibit enabling per-Secret HTTP/HTMX/Detail/search/export before resource-policy enforcement; sensitive path/ID filtering |
| UI/Audit | Violet light/dark/responsive/loading/empty/error, JobExecution outcome, safe audit and Welcome visibility |
| Future feature | Analytics, Intelligence, AlertCases, Reports and mutation pilot remain blocked until implemented and accepted |

Operator retains source/job IDs as sanitized evidence. Record genuine FAIL
as a finding in the owning remediation issue; never bypass protections or
mutate production Vault/Kubernetes for testing convenience. A missing provider
is Not Tested, **not** PASS, No Issues or valid zero.

## Promotion

Review integration → Developer Check on exact SHA → staging PR →
Full Admission → real source-specific UAT and Visual QA/DAST where applicable
→ explicit human acceptance → promotion PR to main → release/tag if needed.

Review currently includes unrelated development; do not promote the whole
review branch merely because Vault source code merged. Reconcile the
admission boundary separately.


## HV-10 PKI expiration snapshot evidence (#2702)

Operator exercises (Not Tested): with approved Vault stored public PKI certificates,
verify one qualified current-generation collection containing expiry at precisely
7 days, after 7 through 30 days, after 30 days, already expired and not yet
valid. Compare the same-source Inventory validity numbers with the Analytics
horizon and record exact commit/collection generation without recording
certificates, identities, paths, CN/SAN, or Secret material.

Verify unauthorized actor with only `secrets_pki.view` receives 403 from the
direct analytics route, as does an actor with only `analytics.view`. No
shortcut via role-aware link or direct GET. Verify disabled or stale source,
opt-out, missing schema, count mismatch and generation mismatch display
Not Qualified rather than zero. Execute Violet light/dark/responsive,
screen-reader label and error-state Visual QA. This does not complete HV-10
historical materialization, lease, authentication or cross-domain analytics.

### HV-06 #2767 — Committed binding coverage UAT (Not Tested)

- Verify Vault Operational Overview reflects separate Metrics Source and
  Alert Source identity validation without changing Vault provider readiness.
- Exercise no binding, configured-but-unverified, stale/future, disabled
  source, invalid profile, wrong canonical identity, multiple qualified
  candidates, partial fleet and over-budget cases. No false healthy zero.
- Verify a qualified binding is not presented as historical retention,
  uptime/HA coverage, active AlertCase, recovery or notification delivery.
- Check source permission/aggregation boundary, responsive light/dark/empty
  states, Developer Check, Full Admission, and real Prometheus/Alertmanager
  DevContainer UAT. No result is marked PASS by this document.
