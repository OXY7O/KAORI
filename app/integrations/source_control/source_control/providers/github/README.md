# GitHub.com GitHub App transport — SC-02

Parent Source Control [#559](https://github.com/OXY7O/KAORI/issues/559);
architecture [#958](https://github.com/OXY7O/KAORI/issues/958);
implementation [#2741](https://github.com/OXY7O/KAORI/issues/2741).
Depends on SC-01 [#2740](https://github.com/OXY7O/KAORI/issues/2740).

This **first transport increment** is intentionally NOT a registered/available
GitHub provider. The canonical provider matrix remains `planned`; the normal
Integrations workspace reuses shared KAORI UI and has no connect/test buttons
until the complete secure registration/validation/JobExecution lifecycle is
admitted.

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

## Subsequent work within #2741

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
- Run existing quality gates, DB/migration checks, end-to-end GitHub.com UAT
  with separate installations and explicit human acceptance on the temporary
  review flow. Official CI/CD, staging and main remain HOLD.

References: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
and https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries

## Increment SC-02 registration and runtime contracts

- `registration.py` checks approved KAORI environment values, credential shape, exact App/installation/account scope, duplicate names/installations, protected App reuse and always revalidates live grant on save. **Save explicitly rejects the provider while the canonical provider matrix remains `planned`**; no unadmitted connection is created.
- `readiness.py` assesses per-capability permission coverage, separately from repository collection. Observed access cannot yield Ready until real worker/inventory/UAT admission.
- `adapter.py` implements unregistered candidate operations for Test Connection, Full Validation and lightweight Runtime Refresh, retaining only sanitized canonical `IntegrationInstance` metadata. There is no job/worker registration or exposed routes yet.
- No new provider-specific UI components exist. When introduced, the provider must reuse KAORI shared Integrations Hero/cards/tables, HTMX, pagination 5, feedback, accessibility and RBAC.

## Durable webhook staging (non-operational candidate)

The migration `20261023_sc_webhook_delivery` adds a **transactional, unique
(installation ID, GitHub delivery UUID)** replay ledger with SHA-256 payload
digest, bounded source hints, received timestamp and processing status.
`webhook_inbox.claim_verified_delivery` authenticates raw bytes using the
App-level protected secret and checks canonical integration/installation
eligibility, then stages an idempotent database record. A repeated delivery
with changed payload is explicitly rejected. The caller must COMMIT before
a separate, scope-qualified reconciliation job is admitted.

No route or worker is wired, no raw payload is retained, no repository fact is
accepted as provider evidence, and no event is sent to Notification Channels.
Webhook ingress is disabled while the GitHub provider is `planned`; SC-03
must implement the follow-up authoritative refresh and committed provider
state, including all/selected repository grant coverage.

## Integration Kernel admission handoff

`kernel_contract.py` holds a typed `IntegrationModule` and
`IntegrationImplementation` constructed from the existing KAORI Kernel
types and the SC-01 `SourceInstallation` record. It maps Test Connection
to inline execution, Full Validation to the existing
`integration-validation` queue and Runtime Refresh to the existing
`integration-runtime` queue. The shared Source Control domain page remains
the detail location; no new provider-specific component is needed here.

The descriptor is **not imported by the Kernel builtin loader**. Its
`register_after_admission()` refuses registration while the canonical GitHub
matrix entry is `planned`. Following reviewed SC-01/SC-02 UAT, a separately
approved workstream must enable the provider, connect the canonical worker
lifecycle, install the reusable forms/HTMX views, prove the webhook ingress
transaction-to-dispatch transition and perform security/visual acceptance.
Draft PR #2766 is not that approval.

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
