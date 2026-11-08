# KAORI Vault — Exact-SHA DevContainer Integrated UAT

**Authority:** HV-09 #2593, child #2843; capability #714; source-specific
HV-01–HV-15 issues; approved DevContainer PostgreSQL procedure
`docs/operations/devcontainer-postgres-first-run.md`. This is an
**operator runbook, not evidence of executed UAT or human acceptance**.

## Admission boundary

Target only `kaori/review/staging-uat` for temporary, local-first,
read-only UAT.
**Official CI/CD admission: HOLD.** The branch also aggregates unrelated work; do not promote
this full branch to official staging/main. Never dispatch official
Developer Check / Full Admission workflows without explicit authority.

**KEEP DISABLED:** Vault privileged provider write pilot (HV-08),
provider-origin AlertCase admission
(`KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED` must be absent/false),
provider-case routing/notifications/recovery, Secret Detail/export,
unapproved live provider mutation and any production Vault/Kubernetes change.

**Known incomplete scopes are not UAT PASS:** HV-04 committed Lease/rotation
history, HV-05 confirmed consumer materialization and verified cutovers,
HV-10 long-term MetricsConsumer Analytics, HV-11 per-asset rules,
HV-12 governed case activation/routing, HV-15 executable canonical
Vault Reports, HV-08 privileged operation pilot. Their current safe
read-only UIs may expose an honest `Not Materialized` state.

## 1. Checkout and preserve evidence

Inside an existing trusted DevContainer:

~~~bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git status --short
git rev-parse HEAD
~~~

Record the **exact tested SHA** (not the SHA printed in this documentation),
date/time, PostgreSQL Alembic revision, local Vault version, target
integration ID, test actor and case, all sanitized job IDs, and login
role. Repeat every test after the branch HEAD changes.

Follow `docs/operations/devcontainer-postgres-first-run.md` for initial
Docker Desktop/VS Code Rebuild/Reopen; inspect database setup health at
`http://localhost:5000/auth/login`. On an **existing, reviewed disposable
DevContainer database only**, run the following from the **Windows host
PowerShell** when a migration is explicitly needed:

~~~powershell
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml config --quiet
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml exec -T db psql -U postgres -d kaori -X -v ON_ERROR_STOP=1 -c "SELECT version_num FROM public.alembic_version;"
~~~

No automatic migration for an existing database. Never run migration as
restricted runtime DB user, alter production DB, stamp a revision, reset
PGDATA, use `down --volumes`, bypass schema/readiness gates or log secrets.
Confirm web + inventory worker + reports/analytics worker readiness via
existing operational health surfaces; queued is not completed evidence.

## 2. Existing quality gates — before opening UAT

Inside DevContainer, run sequentially and **record actual exit codes**:

~~~bash
python -m ruff check app/secrets_pki app/access/scope_policy.py   app/intelligence/alert_signals app/intelligence/alert_intelligence   tests/integrations/test_vault_pki_readiness_freshness.py   tests/integrations/test_scoped_secrets_pki_registry_web.py   tests/integrations/test_secrets_pki_pki_evidence_workspaces.py   tests/integrations/test_secrets_pki_operational_evidence_workspaces.py   tests/integrations/test_vault_integrated_uat_contract.py
python -m ruff format --check app/secrets_pki
python -m pytest -q   tests/integrations/test_vault_provider.py   tests/integrations/test_vault_kv2_committed_inventory.py   tests/integrations/test_vault_pki_committed_inventory.py   tests/integrations/test_vault_stored_certificates_committed.py   tests/integrations/test_vault_pki_readiness_freshness.py   tests/integrations/test_scoped_secrets_pki_registry.py   tests/integrations/test_scoped_secrets_pki_registry_web.py   tests/integrations/test_secrets_pki_pki_evidence_workspaces.py   tests/integrations/test_secrets_pki_operational_evidence_workspaces.py   tests/integrations/test_vault_integrated_uat_contract.py   tests/intelligence/test_vault_alert_observation_snapshot.py   tests/intelligence/test_vault_alert_job_producer.py   tests/intelligence/test_vault_provider_case_plan.py   tests/intelligence/test_vault_provider_case_admission.py   tests/intelligence/test_vault_provider_case_workspace.py
python -m pyright --project pyrightconfig.json
bash scripts/quality_gate.sh --static
~~~

Use the repo's existing `djlint`/Prettier checks via the canonical quality
gates and perform real browser Visual QA. Do not add a custom validator
or skip known failing checks as a passing result.

## 3. Establish safe source evidence

Register and validate one **test-only** Vault AppRole integration via
`Integrations → Secrets Management → Secrets & PKI → Vault`. HTTPS,
trusted CA, approved origins, nonroot ACLs and no raw credentials in
logs/screenshots are mandatory. Use an isolated development Vault,
not production. An unavailable Vault is **Not Tested**, not healthy empty.

Approve explicit KV v2 metadata mounts, public PKI issuer mounts, and
independently opt-in stored public certificate collection. Confirm the
registered canonical **manual safe collection jobs** from
`Platform Operations → Jobs`:

| Registered job key | Expected committed output |
| --- | --- |
| `secrets_pki.inventory.sync` | Current complete metadata-only KV v2 generation |
| `secrets_pki.pki.sync` | Public PKI issuer evidence from approved mounts |
| `secrets_pki.pki.stored_certs.sync` | Opted-in stored public X.509 validity evidence |
| `secrets_pki.vault_alerts.observe` | Explicit qualified Alert Source observation (where configured) |

Confirm the job is registered, worker-ready, authorized, **completed**,
and has sanitized JobExecution evidence. `secrets_pki.vault_alerts.observe`
requires a separate exact Alertmanager binding/selector and supported
correlation key; it must not auto-promote AlertCases, deliver notifications
or infer recovery. Metrics Source binding only qualifies identity, not
retention/HA/historical dataset.

## 4. Browse and verify real operational pages

Use an actor with `secrets_pki.view`, then repeat denied/direct GET
tests using an actor *without* that permission. Permission-specific
read-only pages:

| URL path | Expected behavior and evidence |
| --- | --- |
| `/secrets-pki/` | Four-tab operational Overview: independent source readiness, binding and sample posture |
| `/secrets-pki/inventory` | Qualified KV v2 source coverage/version metadata; no paths/values |
| `/secrets-pki/registry` | Exact active approved **mount** scope: canonical instance ID + opaque policy UUID; mandatory read audit; pages of five |
| `/secrets-pki/lifecycle` | Separate KV v2, certificate validity and TLS candidate assurance |
| `/secrets-pki/certificates` | Public certificate validity; optional TLS correlation only with `tls_certificates.view` |
| `/secrets-pki/pki` | Independently qualified public issuer and stored public certificate populations |
| `/secrets-pki/expiration` | Public X.509 7d/8–30d/after30d windows, not Lease renewal |
| `/secrets-pki/leases` | **Not Materialized** Lease truth; version counts are separate evidence |
| `/secrets-pki/consumers` | **Not Materialized** confirmed consumers/cutover; gated public TLS overlap only |
| `/secrets-pki/governance` | Independent collection and Metrics/Alert binding qualification |
| `/secrets-pki/analytics/certificates` | Additional `analytics.view` required, current generation only |
| `/intelligence/alert-intelligence/vault-cases` | Provider-origin case read page requires `intelligence.view` plus `secrets_pki.view` and exact approved **instance** grant; query parameter `instance_id` |

For Registry, the opaque ScopeAccessPolicy UUID must come from an
approved and effective exact mount-level grant owned by the test actor.
The UUID is **not a bearer token**. Do not grant access by directly
inserting/editing database rows or passing Vault mount/path in the URL.
If the approved Access governance grant workflow is unavailable,
mark this exact scenario BLOCKED/Not Tested and file a remediation issue;
do not bypass #724 for a demo. Vault alert case reads need an **instance**
grant, which does not inherit from a mount grant.

## 5. Mandatory negative scenarios

At minimum verify: no/foreign/revoked/expired/ambiguous grant; user with
global permission but no resource grant; missing/incomplete/stale/future
collection; provider 403/404/503, disabled source, invalid/foreign binding,
wrong TLS permission, direct URL guessing, audit persistence failure,
cross-instance data isolation, idempotent Alert Source replay,
unverified `resolved` status, and source failure after prior success.

The authorized exact-scope Registry read must produce a committed
Activity Audit record. No Secret value, path, namespace, token,
AppRole SecretID, dynamic credential, private key, native alert
fingerprint/HMAC key or raw provider response may appear in browser
HTML, query params, logs, audit, screenshots or exports.

Only an actually successful, complete, fresh empty collection may show
**qualified zero**. Any unavailable/partial/expired result must say
Not Qualified/Unknown; no reset, revoke, heal or notification is inferred.

Verify Violet light/dark, mobile/tablet/desktop, keyboard access,
loading/empty/error state and default five-row pagination. Full UAT
is not complete until provider state, PostgreSQL locking/audit and human
Visual QA are reviewed together.

## 6. Evidence log and decision

Populate a separate record per source/role/scenario without storing
sensitive material:

| Field | Operator entry |
| --- | --- |
| Tested Git SHA / DB Alembic revision | Not Tested |
| DevContainer & Vault versions | Not Tested |
| Source integration (canonical ID only) | Not Tested |
| Qualified collection JobExecution IDs | Not Tested |
| RBAC actor / approved scope grant UUID | Not Tested |
| Real provider positive / negative cases | Not Tested |
| Ruff / Pytest / Pyright / quality gates | Not Tested |
| PostgreSQL row-lock and audit behavior | Not Tested |
| Light/dark/responsive Visual QA | Not Tested |
| HV-01–HV-15 per-scope PASS/FAIL/Not Tested | Not Tested |
| Human reviewer & acceptance date | Pending |

A **FAIL** becomes a finding/remediation issue with owner and evidence.
A **blocked or unimplemented** capability stays Open; tests of its
safe fallback do not make it feature-complete. Maintain exact links
to the issue, branch, commit, PR and collected sanitized evidence.

Do not merge review aggregation to official staging or main as part
of UAT. Human approval + issue-by-issue scope reconciliation precedes
any separate official Developer Check / Full Admission / staging promotion.
