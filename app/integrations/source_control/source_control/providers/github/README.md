# GitHub.com GitHub App — staging lifecycle and SC-02 transport

Parent Source Control [#559](https://github.com/OXY7O/KAORI/issues/559);
architecture [#958](https://github.com/OXY7O/KAORI/issues/958);
implementation [#2741](https://github.com/OXY7O/KAORI/issues/2741).
Depends on SC-01 [#2740](https://github.com/OXY7O/KAORI/issues/2740).

## Current staging provider boundary (2026-11-02)

The canonical provider matrix in `kaori/staging` lists GitHub as **`available`**. The issue-scoped SC-01/SC-02/SC-03 work was subsequently reconciled into the reviewed source, integrated through [#3399](https://github.com/OXY7O/KAORI/pull/3399), and passed Full Admission and staging deployment. The shared `Integrations → Source Control → GitHub` registration, Full Validation/Runtime Refresh, committed inventory and JobExecution plumbing are represented in the accepted staging source. This is **not** proof that a real GitHub App installation completed provider UAT or that hosted Human UAT and broader operational authorization are approved.

- `require_uat_access()` limits installation-specific UAT to active **local database Super Admin** accounts; route-level permission checks also apply. #724 resource-scoped production access remains a separate authority.
- GitHub App/installation/account credentials and provider grants remain authoritative externally. KAORI commits bounded, verified inventory; it must not expose installation tokens or private keys in jobs or responses.
- Signed webhook ingress and the recovery/consumer loop remain independently **default-off** through `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED` and `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED`. Registration and inventory code being admitted never implies a webhook was enabled or that the event was reconciled.
- See the [existing GitHub App Dev Container UAT procedure](../../../../../../docs/operations/github-source-control-devcontainer-uat.md) for historical review-workbench scenarios; new UAT evidence must reference the actual current staging candidate. The older workbench-only HOLD notes do not describe the source already admitted to staging.

## Historical SC-02 transport-only checkpoint

The **first transport increment** was intentionally not registered/available:
GitHub was `planned`, the shared Integrations workspace had no connect/test
actions, and canonical worker/validation admission remained future work.
The sections below retain that incremental history rather than contradicting
the current admitted staging baseline.

## Security and authority boundary

- GitHub.com is the only qualified origin (`https://api.github.com`). GHES
  remains a future explicit profile. No arbitrary user-provided GitHub URL.
- App JSON Web Tokens are signed RS256 with the already-installed
  `cryptography` package; installation tokens are minted with **explicit
  read-only permission downscoping** and retained only in-process.
- The App private key is supplied only by the canonical encrypted credential
  boundary when SC-02 wiring is admitted. Never serialize a JWT, installation
  token, PEM or webhook secret into normalized Source Control inventory,
  JobExecution arguments, logs, screenshots or JSON responses.
- The HTTP transport disables ambient proxy/netrc, requires TLS verification,
  disallows redirects, bounds the response body, uses safe errors and only
  calls the trusted GitHub.com REST API.
- App identity, installation grant, native account and repository selection
  are distinguished. `validate_installation` requires a verified App/installation/
  account match and performs a *single* metadata-only repository-listing probe.
  It is **not** a complete inventory generation.
- `webhook.verify_webhook` verifies GitHub's SHA256 signature with constant-time
  comparison over the original bytes and checks the expected installation ID.
  It returns only a bounded transport envelope. **It does not create provider
  events, save raw webhook payload, accept GitHub source facts, deduplicate
  deliveries or enqueue a task.** Production ingress must atomically record
  delivery identities, enforce App+installation+repository scope and authorize
  an idempotent targeted refresh before any public route may be enabled.
- All/Selected repository grants come from GitHub, never from an invented
  KAORI-side set. Revocation, partial evidence, unsupported permissions and
  API outage must not silently become Ready.

## Historical planned follow-ups within #2741

- Add protected App-config credential storage/reference model by reusing
  `app/security/credentials.py` (not GitHub OAuth SSO); preserve a single App
  configuration across multiple installation grants and independent revocation.
- Implement canonical IntegrationModule/IntegrationImplementation registration,
  implementation records, Test Connection / Full Validation / Runtime Refresh
  and a bounded JobExecution/validation/readiness history contract.
- Build GitHub setup/detail UI using existing Integrations shared Hero, cards,
  tables, modal, pagination, HTMX, status, toast and error/empty/loading states.
  No new Violet primitives, custom pagination, duplicated validation UI or
  GitHub clone.
- Add durable signed ingress and proven scoped event dedup before exposing a
  webhook endpoint; SC-03 owns authoritative repository reconciliation.
- At the original Draft stage, existing quality gates, DB/migration checks,
  end-to-end GitHub.com UAT and explicit human acceptance were still required;
  official staging and main remained HOLD. Current staging admission is noted above.

References: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
and https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries

## Historical SC-02 registration and runtime contract checkpoint

- `registration.py` checks approved KAORI environment values, credential shape, exact App/installation/account scope, duplicate names/installations, protected App reuse and always revalidates live grant on save. **Save explicitly rejects the provider while the canonical provider matrix remains `planned`**; no unadmitted connection is created.
- `readiness.py` assesses per-capability permission coverage, separately from repository collection. Observed access cannot yield Ready until real worker/inventory/UAT admission.
- At this historical checkpoint, `adapter.py` implemented unregistered candidate operations for Test Connection, Full Validation and lightweight Runtime Refresh, retaining only sanitized canonical `IntegrationInstance` metadata. No worker registration or exposed routes existed **at that time**; the current staging implementation is described above.
- At this historical checkpoint no provider-specific UI had yet been introduced. The admitted staging implementation reuses existing Integrations Hero/cards/tables, HTMX, pagination 5, feedback, accessibility and RBAC.

## Durable webhook staging (non-operational candidate)

The migration `20261023_sc_webhook_delivery` adds a **transactional, unique
(installation ID, GitHub delivery UUID)** replay ledger with SHA-256 payload
digest, bounded source hints, received timestamp and processing status.
`webhook_inbox.claim_verified_delivery` authenticates raw bytes using the
App-level protected secret and checks canonical integration/installation
eligibility, then stages an idempotent database record. A repeated delivery
with changed payload is explicitly rejected. The caller must COMMIT before
a separate, scope-qualified reconciliation job is admitted.

At the historical ledger-only checkpoint no route or worker was wired. The
current staged source includes separate gated ingress and worker/recovery code,
but both webhook feature switches are default-off. A transport receipt alone
is not committed repository evidence or a Notification Channels event. SC-03
reconciliation remains bound to independently verified installation grants.

## Integration Kernel admission handoff

`kernel_contract.py` holds a typed `IntegrationModule` and
`IntegrationImplementation` constructed from the existing KAORI Kernel
types and the SC-01 `SourceInstallation` record. It maps Test Connection
to inline execution, Full Validation to the existing
`integration-validation` queue and Runtime Refresh to the existing
`integration-runtime` queue. The shared Source Control domain page remains
the detail location; no new provider-specific component is needed here.

The initial descriptor was **not imported by the Kernel builtin loader**;
`register_after_admission()` rejects `planned` providers. The subsequent
staging integration supplies provider wiring, canonical workers and reusable
forms/HTMX views. Independent webhook ingress/consumer activation, #724 scope
and real provider/security/visual UAT remain gated. The historical Draft
PR #2766 by itself was not admission authority.

The webhook inbox cannot be interpreted as a source event or a notification
event. Only the SC-03 provider collector can commit repository/workflow state
after sufficient scoped GitHub evidence. CDEvents Delivery Intelligence
(#440/#536/#537) consumes those admitted committed records, not raw webhook
JSON or successful API pings.

### Dev Container verification commands (existing KAORI gates)

```bash
python -m ruff check app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_github* migrations/versions/20261023_source_control_*.py
python -m ruff format --check app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_github* migrations/versions/20261023_source_control_*.py
python scripts/verify_migration_graph.py
python scripts/verify_definition_registry.py
python scripts/verify_integration_domain_navigation.py
pytest -q --tb=short tests/unit/test_source_control_identity.py tests/unit/test_source_control_persistence.py tests/unit/test_source_control_github_app_*.py tests/unit/test_source_control_github_kernel_contract.py
python -m pyright --project pyrightconfig.json
```

These are proposed **existing** local quality commands, not evidence they have
run. Run Alembic upgrade/downgrade against the approved disposable Dev Container
database with the project's standard migrations procedure; no live database
changes are authorized by this documentation.


## Historical GitHub App onboarding preview

The application bootstrap registers `github_source_bp` and the existing
`Integrations → Source Control` shared workspace links to it. Routes:

- `GET /integrations/source-control/github/`: provider overview based on the
  existing KAORI Page Hero and Integration overview components.
- `GET /integrations/source-control/github/connections/new`: shared
  registration hero and form for visual/UX review.
- `POST /integrations/source-control/github/connections/new`: server-side
  **HTTP 409** while GitHub remains `planned`, before the submitted form or
  credentials are processed.

Every route uses server RBAC `integrations.manage`, Flask-WTF CSRF for
admitted POSTs, no-store response headers, canonical environment choices,
no secret rehydration and sanitized errors. Once admitted by a future
provider-matrix/Kernel change, Test Connection performs a read-only
identity/scope probe and Save revalidates the grant before committing a
non-ready canonical connection. Live validation, JobExecution/status
presentation, provider promotion and production webhook ingress remain blocked.

At the initial `planned` stage this was a UI review shell with **disabled
actions**, not evidence of real installations. Later SC-03 work added committed
inventory to the staging source; missing inventory or grant evidence must still
render Unknown/Not Observed rather than invented zero counts.
It reuses existing Violet, Hero, domain cards, Flask-WTF, accessibility,
responsive and light/dark classes; no provider-specific stylesheet.


## SC-03 repository worker scope ownership — #4158

Source Control repository admission and the canonical inventory worker use
the **same** `app/integrations/source_control/eligibility.py` predicate and
25-installation bound. The provider's native installation/account/App
credential match, Ready lifecycle, enabled state and host restrictions remain
unchanged. `sync_jobs.py` retains its compatibility imports for existing
callers; `tasks.py` revalidates the same predicate independently of the
dispatcher before any provider request. The task name, id-only Celery payload,
worker registration preflight, scoped UAT administrator requirement and #724
manual access hold remain unchanged. No second synchronization engine or
runtime provider authority was added.

## SC-02 canonical JobExecution admission and committed refresh intents

`job_admission.enqueue_github_app_job` reuses KAORI's existing
`enqueue_instance_validation` and `enqueue_runtime_health_refresh` entry
points. The shared Integration validation subsystem owns JobExecution
durability, Redis resource locks, Celery queue dispatch, status snapshots,
progress, cancellation and existing notifications. No GitHub-specific
Celery worker or job scheduler is created. The bridge fails closed unless:

- The provider matrix is `available` through an approved admission step.
- Canonical `IntegrationInstance`, `SourceInstallation`, App credential,
  host, and account identities match and are enabled/active.
- Integration Kernel resolves the correct registered GitHub provider record.
- An authenticated actor ID and an approved Full Validation or Runtime
  Refresh operation were requested.

Job kwargs contain only the canonical integration type, instance ID and
requester ID; **no App PEM, token, webhook secret or raw delivery payload**.

`reconciliation_intent.resolve_reconciliation_intent` is a second inert
boundary: it qualifies an authenticated, already-committed delivery against
the current committed installation-to-repository grant. Installation grant
changes and unknown/revoked repository hints produce an **installation-grant
refresh intent**, not a repository-targeted mutation. Only a current
committed `granted` relationship qualifies a repository target.

**Handoff is deliberately incomplete while #2742 (SC-03) is pending.**
Neither an intent nor a staged webhook row starts a task, proves it was
queued, or publishes delivery/source/notification evidence. The future
inbox consumer must operate after the delivery DB transaction commits;
it must atomically claim work, use KAORI's registered JobExecution
dispatcher with a bounded SC-03 provider reconciliation task, persist
receipt/status and recover interrupted dispatches. Do not introduce
a parallel task broker, trust payload repository IDs or call GitHub from
a template/render path. The actual after-commit dispatch cannot be
claimed operational until that SC-03 collector and its worker are admitted.

For focused local test execution on the issue branch, add the following
existing pytest modules to the Dev Container validation suite:

```bash
pytest -q --tb=short tests/unit/test_source_control_github_app_job_admission.py tests/unit/test_source_control_github_app_reconciliation_intent.py
```
