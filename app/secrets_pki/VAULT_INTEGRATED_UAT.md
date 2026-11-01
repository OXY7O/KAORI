# Vault / Secrets & PKI — Integrated UAT Acceptance Matrix

Authority: HV-09 #2593; architecture #714; resource scope #724; workstreams HV-01–HV-15.
This document is a test protocol, **not** executed evidence or human acceptance.

For the ordered operator workflow, use [VAULT_DEVCONTAINER_UAT.md](VAULT_DEVCONTAINER_UAT.md) (#2843).

## Exact-SHA evidence requirements

Record the tested Git SHA, DevContainer/target source version, Vault instance
and approved namespace/scope, known test case, JobExecution ID, Alembic HEAD,
worker readiness, sanitized output, test/CI run URL, security-denied actor and
permission, browser light/dark/responsive result, and named human acceptance.
Use PASS / FAIL / Not Tested / Not Implemented explicitly. Never log, export
or screenshot plaintext Secret values, Vault paths/names where sensitive,
SecretIDs, tokens, private keys, dynamic credentials or value hashes.

## Source / verification status (as of 2026-10-23)

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
| HV-07 #2591 / #2678 / #2683 / #2761 / #2826 / #2836 / #2839 | Review candidate: Overview/Inventory/Lifecycle, audited KV v2 Registry, Certificates/PKI/Expiration and evidence-qualified Leases/Consumers/Governance read-only workspaces; authoritative Lease/consumer collectors and Secret Detail remain unavailable | Not Tested |
| HV-08 #2592 | Governed provider operation pilot | Not Implemented |
| HV-09 #2593 | UAT protocol; live scenarios not executed | Not Tested |
| HV-10 #2594 / #2702 | Current-generation public PKI expiration horizon workspace; historical MetricsConsumer datasets/pages absent | Not Tested |
| HV-11 #2595 / #2778 | Review candidate: one population-level qualified PKI public expiry-pressure Intelligence rule; per-asset rules remain unimplemented | Not Tested |
| HV-12 #2596 / #2786 / #2791 / #2798 / #2802 / #2807 / #2813 / #2817 / #2821 | Review candidate: manual Alert Source worker, committed correlation, opt-in admission now requires approved exact-instance scope and normalized role, read-only case workspace rejects unsupported resolved; provider mutation/routing/notifications disabled | Not Tested |
| HV-13 #2597 / #2678 / #2826 / #2817 / #2821 | Canonical #724 exact mount and instance evaluators exist; audited Registry and provider AlertCase read routes are review candidates; detail/export and full scope approval UAT remain pending | Not Tested |
| HV-14 #2598 / #2855 | Role-aware Welcome entry plus Secrets Management Integration sidebar entry and Vault active-state wiring; live navigation/RBAC UAT pending | Not Tested |
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
| Scope/RBAC | Persisted #724 mount/instance evaluators with approved revisions now protect the audited metadata-only Registry and provider-case reads; verify wrong actor/expired/ambiguous grants, audit rollback, direct URL; per-Secret Detail/search/export remains prohibited without separately admitted policies |
| UI/Audit | Violet light/dark/responsive/loading/empty/error, JobExecution outcome, safe audit and Welcome visibility |
| Future feature | Current PKI Analytics and qualified AlertCase read surfaces exist but remain Not Tested. Historical MetricsConsumer Analytics, provider case routing, executable Vault Reports and privileged operation pilot remain unavailable |

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


## HV-12 #2821 — Integrated Alert Source / AlertCase security UAT (Not Tested)

**Review target:** `kaori/review/staging-uat` at the *actual SHA you pull*.
Do not mistake this test protocol, earlier PR merges or static review for UAT PASS.
Do not run official Developer Check / Full Admission or promote the temporary
holding branch before explicit authorization.

### Preflight and focused quality gates

Execute **inside the approved DevContainer** with an initialized, reviewed
PostgreSQL schema and separate inventory worker; record exact SHA, DB
Alembic revision, Celery task registration, actor ID and sanitized JobExecution
public ID. Do not print the HMAC key or provider credentials.

~~~bash
git rev-parse HEAD
python -m ruff check \
  app/access/scope_policy.py \
  app/intelligence/alert_signals/vault_source.py \
  app/intelligence/alert_signals/vault_jobs.py \
  app/intelligence/alert_intelligence/vault_provider_plan.py \
  app/intelligence/alert_intelligence/vault_provider_admission.py \
  app/intelligence/alert_intelligence/vault_case_workspace.py \
  tests/intelligence/test_vault_alert_observation_snapshot.py \
  tests/intelligence/test_vault_alert_job_producer.py \
  tests/intelligence/test_vault_provider_case_plan.py \
  tests/intelligence/test_vault_provider_case_admission.py \
  tests/intelligence/test_vault_provider_case_workspace.py
python -m pytest -q \
  tests/integrations/test_vault_alert_source_binding.py \
  tests/integrations/test_vault_alert_source_qualification.py \
  tests/integrations/test_vault_alert_source_sample_summary.py \
  tests/intelligence/test_vault_alert_observation_snapshot.py \
  tests/intelligence/test_vault_alert_job_producer.py \
  tests/intelligence/test_vault_provider_case_plan.py \
  tests/intelligence/test_vault_provider_case_admission.py \
  tests/intelligence/test_vault_provider_case_workspace.py
python -m pyright --project pyrightconfig.json
~~~

### Source-specific test cases — ALL Not Tested

| Scenario | Expected safe outcome | Status |
| --- | --- | --- |
| Exact Vault Alertmanager source | `vault_instance=<canonical ID>` selector, qualified binding, bounded GET and safe committed snapshot; record JobExecution and generation | Not Tested |
| Missing/disabled/foreign/ambiguous Alert Source | No qualified observation, no unauthorized provider fallback or case changes | Not Tested |
| Missing malformed HMAC key | Manual worker fails closed with generic error; no key in job/audit/log | Not Tested |
| Replayed, duplicate, late, malformed/future or foreign alert | No duplicate case or false recovery; provider failure invalidates previous source evidence | Not Tested |
| **Role only** with all four relevant permissions but no instance grant | Admission `forbidden`; zero AlertCase/Event/AuditEvent writes | Not Tested |
| **Local Super Admin shortcut** without normalized role / exact instance grant | Admission `forbidden`, no inherited scope | Not Tested |
| Exact approved **instance** grant | Only matching Vault ID eligible, no mount inheritance; create max 10 firing cases per invocation; routing suppressed | Not Tested |
| Mount-only, foreign instance, expired, revoked or ambiguous grant | Admission denied, no partial case commit or existence disclosure | Not Tested |
| Same source generation / new severity generation | Replay idempotent; newer severity refresh only with case event and audit | Not Tested |
| Unobserved, suppressed, partial, stale, source 403/503 | Unknown/incomplete, never auto-resolved, auto-closed or notification delivered | Not Tested |
| Tampered `source_state=resolved` in Vault provider case | Entire scoped list unavailable; direct guessed detail URL denied | Not Tested |
| Scoped case list/detail unauthorized, foreign Vault or audit store unavailable | 404/denied; no case data or HMAC provenance leakage | Not Tested |
| Violet light/dark, phone/tablet/desktop, keyboard and HTMX navigation | Read-only UI accessible; paginator defaults to 5; no unsafe mutation controls | Not Tested |
| PostgreSQL concurrent write + grant revocation/read-lock race | Transactional serializability and denial confirmed with real DB, not SQLite alone | Not Tested |

**Security decision gate:** keep
`KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED` **unset/false** outside
approved controlled UAT. No runtime caller currently invokes the writer;
do not add one or enable case routing as part of this review. Independent
#724 scope-policy approval and human acceptance are prerequisites.

For every scenario, capture actual method, expected/actual behavior,
PASS/FAIL/Not Tested, exact SHA, test ID/job reference and sanitized
screenshot or logs. Record genuine FAIL in bounded remediation issues;
do not silently mark skipped tests as PASS.


## HV-07 #2826 scoped registry end-to-end UAT — Not Tested

1. Initialize reviewed DevContainer PostgreSQL schema and one approved Vault
   KV v2 mount with a committed current-generation safe metadata collection.
2. Record the exact SHA and actor permission matrix. Create an approved
   exact mount-level scope policy/revision in Access governance (not in Vault).
3. Open `/secrets-pki/registry`, enter canonical Vault instance ID and
   opaque policy UUID, confirm five-item pagination and mandatory Activity
   Audit before metadata appears. Verify real path/name/value never appears
   in URL, HTML, logs, audit or exported browser data.
4. Verify no-grant, wrong actor/source, instance-only grant, revoked,
   expired, ambiguous grants, disabled/unready source, 403 from Vault,
   incomplete/stale generation and audit-store failures all fail closed.
5. Exercise a fully collected **empty** mount separately; only there is a
   qualified zero acceptable. Verify manual inventory job/reconciliation.
6. Run existing Ruff, pytest, pyright, djlint and light/dark/responsive,
   keyboard and screen-reader Visual QA, capture sanitized evidence.
   Maintain NOT TESTED until executed; no official workflows without approval.


## HV-07 #2836 public PKI evidence workspaces — Not Tested

On an approved real Vault PKI test source, run actual issuer and opted-in
stored public certificate jobs and retain exact-SHA sanitized JobExecution
evidence. Open Certificates, PKI, and Expiration with an allowed
`secrets_pki.view` actor. Verify zero only after a qualified complete
collection; for failed, disabled, stale, partial or missing sources, assert
`Not Qualified` (never inferred healthy), for 7-day and 30-day boundaries
compare against known, non-sensitive test certificate validity dates.

Verify denied `secrets_pki.view` direct GET, separate
`tls_certificates.view` grant/no-grant on the Certificates page,
no source path/issuer identity/serial/subject/PEM/key in HTML,
and no provider request during page rendering. Complete light/dark,
responsive, keyboard/screen-reader and empty/error-state Visual QA.
Execute existing Ruff, djlint, pytest and pyright checks and record
PASS/FAIL per source; all presently Not Tested.


## HV-07 #2839 Operational Leases, Consumers and Governance UAT (Not Tested)

- Verify all three endpoints render with `secrets_pki.view`, direct GET
  denies without permission, and no provider request occurs on page load.
- With no persisted Lease collector, Lease/renewal/revocation counts show
  Not Qualified; actual committed KV v2 versions appear only under clearly
  separate version context, never imply Lease state or successful rotation.
- Without `tls_certificates.view`, Consumers does not query or render TLS
  correlation. With approved permission and fresh current sources, only
  public certificate overlap appears; no confirmed consumer/cutover counts.
  Stale/partial/403 must show Not Qualified rather than zero.
- Governance source populations have independently verified statuses;
  missing Metrics/Alert binding, stale provider, incomplete KV2/PKI and
  ambiguous validation suppress stale counts. No path/policy target identity.
- Validate Violet light/dark/responsive/keyboard/loading/empty states in
  browser and confirm no unapproved mutation action or routing control.
- Execute focused existing check:
  `python -m pytest -q tests/integrations/test_secrets_pki_operational_evidence_workspaces.py`
  plus Ruff/djlint/Pyright and relevant Vault regressions, record exact SHA.
  Human UAT acceptance is still Not Tested, not PASS.


## HV-03/HV-07 #2841 — PKI summary freshness UAT (Not Tested)

At exact testing SHA, exercise issuer and stored public certificate pages
with two approved PKI mounts and committed `ready` collection generations.
Exercise a valid complete zero with both mounts ready, then each negative:
one uncollected, old commit (24h boundary), old observation with fresh
commit, future timestamp, failed/stale retained previous commit, missing
count, over-bound count, inactive provider and unapproved scope. Verify
**no current numeric counts** appear for partial/stale/failed outcomes.
Do not compare to live Vault PKI operations on GET. Capture only sanitized
timestamps, source statuses and test run logs.

~~~
python -m ruff check app/secrets_pki/pki_collection_freshness.py \
  app/secrets_pki/pki_presentation.py \
  app/secrets_pki/pki_stored_presentation.py \
  tests/integrations/test_vault_pki_readiness_freshness.py
python -m pytest -q \
  tests/integrations/test_vault_pki_readiness_freshness.py \
  tests/integrations/test_vault_pki_committed_inventory.py \
  tests/integrations/test_vault_stored_certificates_committed.py \
  tests/integrations/test_vault_pki_validity_posture.py
~~~

All above remain NOT RUN in this GitHub-only source session and cannot
substitute for real Vault/worker/PostgreSQL UAT and human acceptance.


## HV-14 #2855 — Secrets Management Integration navigation (Not Tested)

Using a DevContainer actor with `integrations.manage`, open the
**Integrations** sidebar. The existing domain list must now include
**Secrets Management** exactly once, linking to
`/integrations/secrets-management`. Opening that page or any
`vault.*` route for registration, detail, edit or validation must
highlight the same sidebar child. No top-level Vault-specific menu
or duplicate UI component is created.

Switch to an actor without `integrations.manage`: the navigation
entry must be absent and direct domain/provider requests denied.
An actor having only `secrets_pki.view` must not gain provider
registration rights. Conversely, `integrations.manage` by itself
must not authorize operational Secret Registry or Vault AlertCase
resource reads; those require their independent scoped grants.

Verify keyboard/mobile expanded and collapsed sidebar, Violet dark/light,
breadcrumb domain ownership and link accessibility. Run
`tests/contracts/integrations/test_vault_sidebar_navigation.py`
at the exact SHA and record PASS/FAIL/Not Tested. The unexecuted
GitHub-only implementation remains NOT TESTED until your UAT.
