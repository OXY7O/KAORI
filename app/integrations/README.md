# KAORI Integration Kernel

`app/integrations` is KAORI's provider-neutral integration kernel. It gives the
core a small, stable API while provider implementation remains isolated.

```text
Route → Domain Service → Integration Registry → Adapter → External System
```

## Integration taxonomy

Providers are registered under a stable domain and capability. Taxonomy is
registry metadata, not duplicated persistence on `IntegrationInstance`.

```text
Integrations
├── Orchestration
│   └── Cluster Orchestration
│       └── Kubernetes
├── Observability
│   ├── Metrics
│   │   └── Metrics Source
│   └── Alerting
│       └── Alertmanager
└── Storage
    ├── Object Storage
    │   └── MinIO
    ├── File Storage
    └── Block Storage
```

Vault now extends this product taxonomy as `Secrets Management → Secrets & PKI → HashiCorp Vault`.
Its first provider adapter lives in
`app/integrations/secrets_management/secrets_pki/providers/vault/` and owns only
read-only AppRole identity/health/compatibility evidence under #2585.
KV v2 metadata, PKI, Lease, consumer, Metrics Source, Dashboard, Analytics,
Intelligence, and governed operations remain separately bounded HV-02–HV-15 workstreams.
Vault tokens and plaintext Secret/PKI material are never operational committed state.
Vault authentication relies on approved HTTPS origin/CA, an encrypted AppRole SecretID,
and independently constrained network egress.

`worker_domain` remains execution metadata and must not be reused as the UI or
architecture taxonomy. `app/definitions/catalogs/integrations/taxonomy.yaml` is the canonical domain/capability map; `taxonomy.py` is its validated runtime adapter.

## Physical namespace contract

Folder layout follows the same hierarchy as the persisted integration identity:

```text
app/integrations/
├── orchestration/
│   └── container_orchestrator/
│       ├── frontpage.py
│       └── adapters/
│           └── kubernetes_api/
├── observability/
│   ├── metrics_source/
│   │   ├── adapters/
│   │   │   └── prometheus_http/
│   │   ├── binding_validators/
│   │   └── query_profiles/
│   └── alert_source/
│       └── providers/
│           └── alertmanager/
└── storage/
    ├── object_storage/
    │   ├── adapters/
    │   │   └── s3/
    │   └── providers/
    │       └── minio/
    ├── file_storage/
    └── block_storage/
```

The rules are deliberate:

- domain and integration-type directories are stable architecture names;
- a product name may appear only in a provider implementation or provider definition;
- a reusable protocol/API belongs under `adapters/<adapter_key>/`;
- providers that share an adapter reuse that adapter rather than copying transport code;
- provider-neutral routing, bindings, query profiles, and consumer contracts stay at the integration-type level;
- application workspaces mirror the same intent: `app/integrations/observability/metrics_source/application`, `app/integrations/observability/alert_source/providers/<provider>/application`, and `app/integrations/storage/object_storage/providers/<provider>/application`;
- templates and definition catalogs mirror the same domain/integration-type/provider hierarchy.

For example, Prometheus and Thanos share `prometheus_http`; MinIO, Garage, and AWS S3 can share the `s3` adapter; Rancher and Sangfor Kubernetes Engine can reuse `kubernetes_api` after producing or resolving a Kubernetes API connection. Adding a provider must not create a new product directory directly under `app/integrations`.


## Navigation projection

The sidebar renders domain workspaces from the canonical taxonomy:

```text
Integrations
├── Overview
├── Orchestration
├── Observability
├── Storage
├── Registry
├── Secrets Management
└── Notification Channels
```

Product-specific pages remain provider workspaces beneath those domains. Each registered
`IntegrationModule` declares `navigation_endpoint_prefixes`, allowing deep routes such as
`cluster.*`, `metrics.*`, `alertmanager.*`, and `vault.*` to retain
the correct domain active state without provider-name branching in the
sidebar template. The rendered sidebar uses
`app/common/workspace_navigation_catalog.py` and
`app/common/workspace_navigation.py`, not the older
`components/navigation/integrations_menu.html` partial. New taxonomy
domains need a permission-aware workspace capability there until the
separate #624 navigation redesign is accepted; provider products do not
become top-level sidebar entries.

## Binding model

Bindings remain asset-centric and provider-neutral:

```text
IntegrationInstance ── IntegrationBinding ── Managed Asset
                          asset_type
                          asset_key
```

A provider does not persist a direct foreign key to another provider. Multiple
providers may bind to the same asset and serve different capabilities. For
example:

```text
Kubernetes Cluster
├── Kubernetes API provider
├── Metrics Source
└── Alertmanager alerting provider

Object Storage System
├── MinIO API provider
├── Metrics Source
└── Alertmanager alerting provider
```

New domains must reuse `IntegrationBinding`; do not introduce pair-specific
binding tables such as `minio_metrics_bindings`.

## Rules

- Cross-domain callers resolve integrations with `get_integration()` or
  `execute_integration_operation()`.
- Provider-specific code lives under the matching `providers/<provider>/` namespace; reusable transport/API code lives under `adapters/<adapter_key>/`.
- Every provider registers `domain_key`, `capability_key`, catalog metadata,
  canonical-record reverse loading, workspace routing, queue ownership,
  capability keys, and compatibility profiles through `IntegrationModule`.
- UI/domain packages may contain forms, route handlers, presentation builders,
  and provider-specific business workflow, but they must not duplicate clients,
  adapters, credentials, bindings, or runtime persistence.
- Every asynchronous operation uses `JobExecution` and an explicitly mapped
  queue.
- SQLAlchemy models remain centralized under `app/models/`.
- Retired bookmark routes are removed; canonical integration URLs are the only supported entry points.

## Shared contracts

- `contracts/base.py`: runtime and operation adapter protocols.
- `contracts/capabilities.py`: capability declarations and evidence contract.
- `contracts/results.py`: provider-neutral runtime and operation results.
- `contracts/exceptions.py`: stable orchestration exceptions.
- `app/definitions/catalogs/integrations/`: versioned provider, compatibility, consumer-profile, and taxonomy definitions.
- `taxonomy.py`: validated runtime adapter for stable integration domains and capabilities.
- `registry.py`: registration, taxonomy ownership, lookup, dispatch, model
  loading, detail routing, failure hooks, and queue map.
- `binding_service.py`: provider-neutral source-to-asset binding entrypoint.

## Validation levels

KAORI separates provider validity from consumer eligibility. Provider readiness
must never depend on one downstream domain/exporter family.

```text
Provider
  → Compatibility Profile
  → Provider Capability Set
  → Core Validation
  → Provider Ready
  → Asset Binding
  → Consumer Profile
  → Binding Validation
  → Consumer Eligibility
```

1. **Test Connection** verifies submitted endpoint identity and reachability.
2. **Provider Core Validation** resolves the provider compatibility profile,
   validates provider-owned capabilities, and persists provider evidence through
   `integration-validation` workers. It is consumer-neutral.
3. **Binding Validation** proves that one ready provider can serve one managed
   asset. The asset binding selects a consumer profile, selector, and validation
   evidence without changing provider readiness.
4. **Consumer Eligibility** combines provider-core execution capability evidence with validated binding evidence for the asset. Transport/query capabilities remain provider-owned; metric/selector evidence remains consumer-binding-owned.
5. **Runtime Refresh** performs lightweight provider health observation using
   `integration-runtime` workers and does not replace Core or Binding Validation.

The full-validation worker dispatches through the registry and does not branch
on provider names. Providers with `binding.validate` automatically participate
in binding refresh. Provider-specific failure persistence is exposed through a
registered hook.

Compatibility profile and consumer profile are different contracts:

- **Compatibility profile** answers whether the detected product/version/API
  contract is supported by KAORI and which provider capabilities can be
  validated.
- **Consumer profile** answers what asset-specific evidence is required after a
  binding exists.

Metrics Source is the canonical metrics abstraction. `provider_key` records product
identity, `adapter_key` selects the backend implementation, and `query_language`
records the source query contract. `observability/metrics_source/binding_profiles.py` selects consumer
validation by `adapter_key + asset_type`: Kubernetes registers
`kubernetes-metrics-v1`; Object Storage registers the provider-neutral
`object-storage-metrics-v1`. Consumer validators may then resolve provider-qualified
evidence contracts such as MinIO Metrics v2 without leaking backend products into
the generic binding registry.

Alertmanager follows the same boundary. Provider Core Validation proves only the
Alertmanager API contract. `observability/alert_source/providers/alertmanager/binding_profiles.py` resolves
`kubernetes-alerts-v1`, `object-storage-alerts-v1`, and future alert consumer profiles by
asset type. Non-global bindings own their alert identity selector and validation
evidence, allowing one shared Alertmanager to safely serve multiple alert families.

See `docs/architecture/integration-module-map.md` and the README inside each
provider module.

### Metrics Source identity and horizon routing

Metrics Source is one canonical integration category. Product identity is supplied by
the provider catalog and persists as `MetricsSource.provider_key`; backend execution is
selected by `adapter_key`; query semantics are declared through `query_language`.
Operator registration uses one provider-neutral route family under
`/integrations/observability/metrics-sources/`.

A metrics consumer may bind multiple eligible sources to the same asset. Every binding
owns a provider-neutral routing policy:

```text
query_horizon = recent | historical | balanced
weight        = 1..100
```

`METRICS_RECENT_WINDOW_HOURS` defines the recent-data boundary (24h by default).
Instant/current queries request the recent horizon. Point-in-time and range queries
select recent or historical from their actual time boundary. Resolution is deterministic
and safety-first: eligibility and runtime health are evaluated before horizon preference;
role (`Primary → Secondary → Fallback`) remains the failover tier; routing weight ranks
sources inside the same horizon and role; lower priority breaks remaining ties. A horizon
mismatch is a fallback, not a hard rejection.

Current provider definitions may use different default horizons, but consumer code never
branches on provider labels. Adding another product that uses an existing adapter is a
catalog change; adding a different protocol/query language adds an adapter/profile while
the DB, routes, resolver, bindings, and consumer domains remain unchanged.

## UI workspace contract

The implemented Integrations presentation and interaction contract is `docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md`. The original findings and implementation disposition are recorded in `docs/design/audits/INTEGRATIONS_FULL_AUDIT_20260731.md`.

Shared Integrations templates own semantic status adaptation, registry controls, loading, pagination, and bright-evidence hierarchy. Provider packages retain factual compatibility, capability, binding, runtime, and lifecycle data. Provider-local runtime-history presentation wrappers and secondary semantic palettes are not allowed.

### Domain landing projection

`/integrations/orchestration`, `/integrations/observability`, and `/integrations/storage` share the same taxonomy-driven landing workspace:

```text
Capability Registry
Provider Registry
Bindings
```

The Provider Registry is built from canonical `IntegrationInstance` rows. The Bindings view contains consumer-source relationships only; native asset-owner/provider relationships are represented by Provider Registry/managed-asset ownership and are never duplicated as self-bindings. Cross-domain sources appear when they target an asset type owned by the domain taxonomy. Provider-specific ORM queries are not allowed in the shared domain service.

Metrics Source and Alertmanager own binding mutation for their respective source families. Kubernetes and MinIO surface bound observability sources as read-only lifecycle inventory. Eligible asset families are registered centrally in `app/integrations/consumer_assets.py`, so adding a future asset such as Vault extends source binding/coverage by adding the asset definition plus compatible consumer profiles instead of a new binding table or product-specific source form.



## Bindings & Consumers Final Lock

Metrics Source and Alertmanager are source-owned mutation workspaces. Their binding registries expose Consumer Asset, provider identity selector, Consumer Profile, Resolver Preference, Binding Validation, Effective Resolution, and Actions with canonical pagination/loading behavior. Resolver preference is safety-first. Metrics sources add query-horizon routing: eligible/healthy sources are ranked by horizon match, then `Primary → Secondary → Fallback`, then routing weight, with lower numeric priority breaking remaining ties inside the same role/weight.

A saved binding starts in `Validation Required`. Selector changes clear stale binding evidence and return the record to `Validation Required`; only the explicit binding `Validate` action rebuilds consumer-specific evidence. Provider Full Validation is intentionally provider-core only and never revalidates consumer bindings implicitly. Object Storage binding validation additionally persists canonical metric-family, label-schema, and executable-query readiness so Analytics can distinguish contract gaps from current runtime reachability. Kubernetes and Object Storage inventory/lifecycle pages show the relationship read-only and link operators back to the source workspace for mutation.


## Notification Channels — durable delivery recovery (#1431)

New outbound attempts commit their `notification_deliveries` journal row as
`queued` with `attempt_count` incremented **before any provider request**;
the result is committed separately. An encrypted transport/message snapshot
is embedded in the existing journal JSON field (no schema migration). The
snapshot is encrypted using the canonical
`INTEGRATION_CREDENTIAL_KEY` rotation contract and is not exposed in
Delivery Activity or Activity Audit.

Recovery uses the existing maintenance Celery queue with one PostgreSQL
`SKIP LOCKED` claim at a time (maximum 25 rows per invocation).
`NOTIFICATION_DELIVERY_RECOVERY_ENABLED=false` is the safe default during
DevContainer review; set it to `true` only after UAT approval.
`NOTIFICATION_DELIVERY_RECOVERY_INTERVAL_MINUTES` defaults to 1 (1–60),
`NOTIFICATION_DELIVERY_RETRY_DELAY_SECONDS` to 180 (120–86400,
longer than the maximum provider transport timeout), and existing
`NOTIFICATION_DELIVERY_MAX_ATTEMPTS` remains the bounded attempt budget.
Recovery is independent of Alert Intelligence scheduling. Legacy records
without the committed encrypted snapshot cannot be reliably replayed; policy,
credentials and destination are rechecked before any attempt.

**Guarantee: at-least-once attempts, not exactly-once provider delivery.**
A worker interruption after remote acceptance but before committing its result
can still cause a duplicate provider message. A `sent` journal row and unique
channel/event identity suppress committed duplicates, but providers are external
authorities and may not support remote idempotency. Do not enable the recovery
schedule until Celery worker/Beat, database crash injection, secret rotation,
test-adapter delivery, duplicate/concurrency and human acceptance are verified.


## Telegram Forum Topics — Notification Channels (#1454)

The Telegram provider in **Integrations → Notification Channels** supports an optional
numeric `message_thread_id` (Forum Topic ID) alongside the existing `chat_id`
and encrypted bot token. The chat ID identifies a supergroup or chat;
`message_thread_id` targets an existing **Topic** within a Telegram Forum
supergroup. KAORI does not create/manage Telegram topics or treat them as
new integration providers.

Configure a single private **KAORI** supergroup with Topics enabled and create
separate Telegram topics such as **🚨 Alert**, **🔄 GitHub**, and **💬 Diskusi**.
For application alerts create one notification channel pointing to the supergroup
and **Alert** Topic ID; select only the intended domain/event types in its policy.
Leave Topic ID empty for ordinary Telegram chat/group/channel destinations.

**GitHub Actions Topic remains separately authoritative** under issue #64:
`.github/workflows/telegram-github-actions.yml` and
`scripts/ci_delivery_notify.py` use GitHub repository secret
`TELEGRAM_BOT_TOKEN` plus `TELEGRAM_CHAT_ID` /
`TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`. Do not duplicate GitHub events through
the application Notification Channels catalog. The discussion topic belongs
to Telegram's human conversation and needs no KAORI application channel.

Topic IDs must be positive integers (1–2147483647); invalid configurations
fail closed rather than accidentally posting to the general supergroup.
The Topic ID is ordinary provider configuration (not a secret). It is preserved
for edit and transport replay; changing or clearing it resets channel validation
through the existing `update_channel` transport-change check. Always run
**Test Delivery** after modifying a Topic ID and confirm the message arrived
in the intended topic before enabling operational use. Existing channels with
no Topic ID keep their chat-only behavior. Replayed deliveries obey the
existing provider_config snapshot/transport mismatch guard. No migration
or global delivery worker change is required.


## Notification Channels — approved hybrid provider roadmap (#1456)

**Status: Phase 1 provider source merged to review; runtime UAT/admission pending.**
KAORI's delivery capability is **hybrid**: internal/self-hosted operational push
and popular team collaboration endpoints use one existing
`Integrations → Delivery → Notification Channels` governance surface.
The three **pre-Phase-1** adapters are Telegram (including Telegram
Forum Topic ID), Email/SMTP, and Microsoft Teams Workflows. Phase 1 adapter
code for **ntfy, Slack, and Discord** is now merged on
`kaori/review/staging-uat`, but has not completed runtime UAT or staging admission. GitHub Actions'
trusted-branch Telegram notifier retains its separate GitHub ownership (#64);
a second application-based CI notifier must not duplicate those messages.

### Sequencing and workstreams

| Phase | Provider | Role | Delivery authority |
| --- | --- | --- | --- |
| **1 / first** | **ntfy** — [#1458](https://github.com/OXY7O/KAORI/issues/1458) | Owned/self-hosted push to a protected topic, including mobile subscribers | ntfy server and client remain authoritative for receipt/subscription |
| **1 / second** | **Slack Incoming Webhooks** — [#1459](https://github.com/OXY7O/KAORI/issues/1459) | Popular enterprise/team-channel delivery | Slack workspace and bound webhook channel |
| **1 / third** | **Discord Webhooks** — [#1460](https://github.com/OXY7O/KAORI/issues/1460) | Developer/ops community channel delivery | Discord owns guild/channel and messages |
| **2 / candidate** | Gotify, Mattermost, Google Chat | Additional self-managed push and enterprise collaboration | Respective external systems |
| **3 / candidate** | Matrix, PagerDuty | Federated messaging and on-call escalation | Matrix rooms / PagerDuty incident lifecycle |

Phases 2–3 are **candidate evaluation only**, not build commitments.
Gotify overlaps the first self-hosted push use case: assess demand and
operational value after ntfy acceptance rather than implementing two
near-identical transports at once. PagerDuty stays authoritative for
acknowledgement, escalation policies and incident state. Separate
provider-specific issues are required before any implementation starts.

The approved provider plan is parent [#1456](https://github.com/OXY7O/KAORI/issues/1456).
This documentation is the bounded task
[#1457](https://github.com/OXY7O/KAORI/issues/1457);
the three Phase 1 provider issues are independent implementation authorities.
Their order is an **execution priority, not a `blocked by` dependency**
between ntfy, Slack and Discord.

### Shared delivery contract — no new architecture

- Extend the existing `NotificationProviderAdapter` catalog with one
  domain-owned provider adapter/form per supported service. Keep
  `NotificationChannel` instances provider-neutral; one instance represents
  a specific approved destination. No separate notification product, provider
  database schema, or generic arbitrary-URL webhook sender.
- Reuse `integrations.manage`, CSRF, server-side field validation, encrypted
  credential storage, secret-free form edit and audited configuration lifecycle.
  Every provider has a **Test Delivery** path; changing destination, transport
  or credentials resets validation and must not auto-enable delivery.
- Event routing retains the existing domain/event/severity catalog
  (`app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml`).
  Do not invent new source events or clone external provider state as an
  implementation shortcut. GitHub Actions notification authority remains
  independent of the application catalog.
- Reuse committed `NotificationDelivery` event identity, status, attempt
  count, provider-result evidence, redacted failures and encrypted transport
  snapshot. Delivery remains **at least once**, not exactly once. The bounded
  Celery recovery worker must remain **opt-in / disabled by default**
  (`NOTIFICATION_DELIVERY_RECOVERY_ENABLED=false`) until explicit UAT
  authorization. Do not claim a provider accepted a message as proof a human
  or mobile client received or read it.
- Use KAORI shared Violet UI/UX components, provider-specific setup guidance,
  compact actionable messages, light/dark/responsive forms, accessible dialogs,
  standard loading/error/toast/empty state and pagination **5 by default**.
  Provider-specific runtime quirks belong in their adapter, not a second UI.
- All outbound transports need bounded timeouts/payloads, secure TLS/trust,
  destination authorization, redirect restrictions, secret-free errors/logs,
  retry/rate-limit classification, and threat-modelled egress. **ntfy internal
  servers are allowed only through an explicitly governed internal-endpoint
  policy** with approved CA/trust; do not turn this into unrestricted
  private-network access or a TLS-verification-off toggle. Credentials and
  secret-bearing webhook URLs must not leak into URLs, logs, HTML, activity
  metadata, debug errors or delivery journal.

### Phase 1 provider-specific boundaries

**ntfy:** server-managed HTTPS base URL + topic, optional encrypted access
token or approved authenticated publishing; publish title, body, bounded
priority and safe KAORI link. Validate topic/URL, internal PKI, destination
policy and redirect/network protections without breaking approved self-managed
servers. Do not implement subscriptions, mobile receipts or a self-hosted
ntfy server inside KAORI. Publishing API:
https://docs.ntfy.sh/publish/ .

**Slack:** channel-bound Incoming Webhook with encrypted secret URL.
Validate official endpoint and forbid redirects/host switching; normalize
provider errors and bounded HTTP 429 / `Retry-After` behavior. No Slack
OAuth user impersonation, chat history mirroring, arbitrary channel override,
or fabricated message acknowledgement. Official docs:
https://api.slack.com/messaging/webhooks ;
https://docs.slack.dev/apis/web-api/rate-limits/ .

**Discord:** channel-bound webhook with encrypted token/URL and outbound
allowlist, bounded content/embeds, `allowed_mentions` denying mass pings by
default, and rate-limit aware provider status. No Discord full bot,
server-directory access, DMs or chat history. Official references:
https://discord.com/developers/docs/resources/webhook ;
https://support-dev.discord.com/hc/en-us/articles/6223003921559-My-Bot-is-Being-Rate-Limited .

### Review / UAT boundary

Each provider gets its own branch/PR, tests, mocked transport-negative paths,
DevContainer safe destination UAT, permission and secret-redaction checks,
desktop/mobile/light-dark accessibility evidence and human acceptance. For
self-hosted ntfy include trusted internal CA and blocked unsafe endpoint cases;
for Slack/Discord include redirect/revocation/429/secret-leak cases.
**Three new Phase 1 adapters are integrated to the review branch only; this does not authorize deployment or live provider use**. Under the
current review session, CI/CD, Developer Check, Full Admission, DAST,
`kaori/staging`, `main`, deployment and release are **HOLD** pending explicit
authorization. A review-only documentation merge is not staging UAT acceptance.


### Phase 1 provider setup and UAT notes (#1473)

**Status:** review-only adapter source integrated via ntfy PR #1468, Slack PR
#1471 and Discord PR #1472. Existing three providers are unchanged.
Provider availability on the review UI is **not** proof of live connectivity,
permissioned destination ownership, UAT acceptance or release readiness.

**ntfy, self-hosted:** Set `NOTIFICATION_NTFY_ALLOWED_ORIGINS` on the KAORI
web process and Celery worker to explicit comma-separated HTTPS server origins,
for example `https://notify.internal.example`; when unset, destination
validation and delivery fail closed. Optionally provide a trusted PEM bundle
using `NOTIFICATION_NTFY_CA_BUNDLE` for your internal PKI. Never disable TLS
certificate verification. Explicitly restrict DNS resolution and network
egress at infrastructure policy: the application origin allowlist plus
redirect denial does **not** protect against all malicious DNS changes.
Create a protected topic and optional publish-scoped access token, configure
the channel with that approved origin and topic, then Test Delivery to an
operator-owned subscriber. Server acknowledgement does not prove mobile
receipt or human reading.

**Slack:** Configure an official, channel-bound Incoming Webhook on
`hooks.slack.com` (or approved GovSlack host), store its secret URL only in
the password field, and assign a human destination label. Webhook ownership
determines the Slack channel; do not assume the label changes the destination.
Credentials are encrypted and never rendered back. Validate the destination
and Test Delivery against a sanctioned sandbox, then confirm channel receipt.

**Discord:** Configure an official `https://discord.com/api/webhooks/...`
Execute Webhook with minimum privileges. Store its secret URL through the
password field; Test Delivery before enabling the channel. The payload
includes `allowed_mentions: {"parse": []}` to suppress accidental user,
role and mass mentions. No Discord bot, chat history, guild discovery or
subscriber-read status is replicated.

**Reliability boundary:** Slack and Discord classify HTTP 429 with sanitized
provider failures. The existing opt-in journal recovery currently uses the
KAORI bounded retry delay; it does **not yet honor provider-specific
`Retry-After` scheduling deadlines**. Do not claim rate-limit-compliant
retry, exactly-once remote delivery, or production readiness. Governed
follow-up work must address provider-specific deadlines and concurrent
claims before enabling `NOTIFICATION_DELIVERY_RECOVERY_ENABLED=true`.
Keep `NOTIFICATION_DELIVERY_RECOVERY_ENABLED=false` during DevContainer
review.

**UAT still pending:** run existing regression suites, provider mocked
transport tests (2xx, 4xx, 429, redirects, timeouts, TLS, invalid secret),
explicit ntfy internal network/CA tests, Flask permission/CSRF checks,
responsive/light-dark/keyboard Visual QA, and permitted sandbox Test Delivery
on authorized destinations. Do not advance staging/main promotion or claim
human acceptance without evidence.

### REVIEW(5) — Configured Channels registry (#2318)

The notification channel registry now follows canonical `table_registry.filter_form`
with live HTMX search by channel name, provider and enabled/disabled state,
conditional `clear_filters_link`, server-side filters before pagination, default
Rows 5, and query-preserving footer. Filtered empty results differ from a
truly unconfigured channel inventory. Native GET remains the non-HTMX fallback.
Name filtering deliberately avoids encrypted provider credentials, destination
secrets and arbitrary provider calls. The existing read-only channel table,
permission-gated Edit/Test/Delete actions, status computation, source-owned
provider catalog and Activity Audit remain authoritative.

### REVIEW(5) — Delivery Activity canonical filter (#2319)

Delivery Activity already has persisted rows, status/evidence columns,
loading and pagination. The Exact Event Key filter now uses existing
`table_registry.filter_form` auto-apply HTMX after input changes and
`clear_filters_link` for active filters instead of the bespoke Find
Deliveries submit button. Scoped `notification-delivery-registry` swaps,
loading indicator, latest-request-wins synchronization and tab/Rows
preservation follow the shared component, retaining native GET fallback.
The **exact event-key** match and permissioned Report source links remain
unchanged. Delivery history remains provider evidence, not extra authored
Activity Audit. Firefox/Dev Container and human acceptance remain pending.

### REVIEW(5) — Provider controls and modal header (#2320)

Provider cards now use canonical secondary action-button geometry for
Guide and Configure (icon-first, 40px, hover/focus/active), with
provider-specific accessible names. Existing Alpine/native dialog behavior
is unchanged. Provider Setup Guide has a shared 'Guided Setup' metadata
label beside its title. No changes to provider adapter, credentials,
permissions or outbound delivery; Dev Container browser UAT pending.

### REVIEW(5) — Add Notification Channel modal and setup guidance (#2321)

Create Channel displays the canonical `New Destination` header label and a
catalog-driven selection gallery for all six supported transports (Discord,
Slack, ntfy, Telegram, Email/SMTP and Microsoft Teams). Choosing a card sets
the existing Alpine-bound native Provider selector and exposes the
unchanged adapter-owned destination/credential form. Edit Channel retains
its immutable provider and actual saved state; CSRF, form validation and
encryption of secrets are unchanged. Prior to selection, existing credential
and activation boundaries are visible instead of a sparse, obsolete prompt.

Provider-owned Setup Guide sequences, credential security boundaries and
Test Delivery interpretations are now concise action-and-purpose sentences.
The complete ntfy allowed origin/CA/network requirements, Telegram topic
and separate GitHub notifier boundaries, Slack/Discord HTTPS constraints,
SMTP TLS/password safeguards and Teams Anyone trigger requirement stay
explicit. A two-line display is a Firefox Lenovo L13 review target, **not**
a forced clamp or a runtime PASS; narrower viewports may wrap further.
Focused local provider and Jinja contracts, real browser Visual QA and
human acceptance remain pending; official gates/deployment HOLD.

### REVIEW(6) — Modal simplification and delivery policy (#2329)

Provider selection is now **single-source via the existing native Provider
dropdown**, with no duplicate six-card gallery. Add/Edit and Setup Guide
modal headers show contextual metadata immediately below their descriptive
subtitles. The redundant Minimum Alert Severity helper sentence is removed
from the UI while its catalog-owned `severity_scoped` backend logic stays
unchanged. Delivery Domains show a compact full-width row of actual
source-supported routing domains; Allowed Uses use a responsive 2-/3-column
checkbox grid instead of a tall narrow rail. Preserve all selected values,
server form validation, CSRF, current provider form partials, enabled-state
contract and accessibility. The baseline catalog authorized Kubernetes and Object Storage. Review-only
#2342 adds the published Reports domain **Artifact Registry**
(`artifact_registry`) with `report.generated` as its sole qualified event.
This is distinct from Alert Intelligence's `registry` domain, whose
firing/resolved routing remains denied under #1186/#1512. Existing
Kubernetes/Object Storage event policy stays unchanged; all further
new-domain routing still requires producer/authority audit #2331, not
a fabricated UI-only checkbox.
No official admission until Dev Container functional/visual UAT and human
acceptance are captured.

### REVIEW(6) — Setup Guide copy density (#2330)

The source-owned security and Test Delivery notes for all six provider
adapters now use concise explanatory statements rather than multi-sentence
paragraphs. Discord and Slack still require official HTTPS and forbid
redirect/proxy relaxation; ntfy retains approved origins, CA bundle,
verified TLS and egress limits; Telegram preserves separate GitHub Actions
ownership, credentials and forum topic caveats; Email retains
STARTTLS/SMTPS/trusted relay; Teams retains the Anyone trigger and secret
Workflow URL handling. Test Delivery indicates provider acknowledgement,
not guaranteed human reading. The long ntfy origin instruction is shortened
without losing its required environment variable or app/worker scope.
Actual two-line text wrapping depends on browser/viewport; real Firefox
Visual QA and human acceptance remain pending, with no forced line clamp.
