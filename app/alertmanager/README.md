# Alertmanager Integration Foundation

## Purpose

`app/alertmanager` is KAORI's provider-neutral integration layer for
Alertmanager deployments that already exist and remain managed outside KAORI.
It supports a reusable connection lifecycle across infrastructure assets,
services, operational domains, and workflows. A registered connection may be
standalone, externally managed, shared, or managed for a specific operational
scope. Governed bindings determine where the connection is eligible for use.

Alertmanager remains authoritative for alert grouping, routing, inhibition,
silences, receivers, and notification delivery. KAORI does not replace those
functions. KAORI owns connection configuration, validation, capability
discovery, safe provider reads, source-to-asset bindings, normalized provider
records, centralized visibility, operational audit, and downstream consumption
by analytics or intelligence domains.

The current adapter is intentionally read-only. It calls Alertmanager API v2
for status, alerts, and silences. It does not create silences, modify routing
configuration, change receiver configuration, or manage the Alertmanager
process lifecycle.

## Implemented architecture

The integration is now instance-first instead of cluster-owned:

```text
Existing Alertmanager deployment
        ↓
AlertmanagerInstance
  connection, authentication, TLS, validation, capabilities
        ↓
AlertmanagerBinding
  scope type, scope key, source role, priority
        ↓
Consumer facade
        ↓
Operational analytics, governance, automation, and intelligence workflows
```

An Alertmanager deployment is registered once. One or more bindings determine
which infrastructure scopes may consume it.

Examples:

```text
Central Alertmanager
├── kubernetes_cluster:cluster-a   primary
├── kubernetes_cluster:cluster-b   primary
├── server_group:linux-production  primary
└── storage_service:minio-prod     primary
```

`scope_type` and `scope_key` are canonical integration contracts. Managed
clusters use a first-class selector, while other infrastructure assets,
services, platform environments, and global operational contexts use canonical
keys without changing the provider model.

## Provider and operational-domain boundary

```text
app/alertmanager
→ understands Alertmanager API, connection, status, alerts, and silences

consumer domains
→ interpret canonical alert records for their own assets, services, ownership,
  governance, incident readiness, automation, and correlation requirements
```

Generic normalization must not add consumer-specific resource fields or
operational assumptions at the provider layer. Asset and service interpretation
belongs to the consuming bounded context.

## Persistence model

Database models remain centralized in `app/models/alertmanager.py`.

### `AlertmanagerInstance`

Represents one reusable provider connection. It owns:

- instance identity and deployment type;
- endpoint and authentication mode;
- TLS verification and timeout;
- enabled/disabled lifecycle state;
- detected version;
- endpoint and capability profiles;
- readiness and validation state;
- sanitized runtime health metadata; and
- one-to-many asset bindings.

### `AlertmanagerBinding`

Maps one instance to an infrastructure scope. It owns:

- `scope_type`;
- `scope_key`;
- source role: `primary`, `secondary`, or `fallback`;
- priority;
- enabled state; and
- the instance relationship.

Only one enabled primary Alertmanager source is allowed for a given scope.
Secondary and fallback bindings may coexist. Runtime resolution orders primary,
secondary, and fallback sources by role and priority.

### Legacy compatibility model

`AlertmanagerConfig` remains temporarily because existing installations and
external imports may still use the former one-config-per-cluster model.

Migration `20260718_alertmanager_instances`:

1. creates `alertmanager_instances`;
2. creates `alertmanager_bindings`;
3. backfills one instance for every configured legacy cluster Alertmanager;
4. creates a primary `kubernetes_cluster` binding for that cluster; and
5. keeps the legacy table for a controlled compatibility window.

New integration pages write only to the instance and binding model. Legacy
cluster URLs resolve or materialize an instance and redirect to the canonical
instance page. The legacy table must be removed only in a later migration after
all external consumers have completed the cutover.

## Compatibility and readiness

KAORI validates the following Alertmanager API v2 operations:

```text
GET /api/v2/status
GET /api/v2/alerts
GET /api/v2/silences
```

API v1 is not used.

Profiles:

- endpoint profiles: `alertmanager-api-v2-legacy` and
  `alertmanager-api-v2-current`;
- capability profile: `alert-management-v1`.

Readiness states:

```text
validation_required
ready
degraded
blocked
disabled
```

Saving connection settings resets readiness to `validation_required`. Runtime
consumers do not use a disabled, blocked, or unvalidated source. Validation
persists the detected version, compatibility result, verified capabilities,
response time, and a sanitized operational message.

## Registration contract

The Register Alertmanager Instance page uses a mandatory two-step pre-save
contract:

```text
Administrator completes the connection form
        ↓
Administrator clicks Test Connection
        ↓
KAORI calls GET /api/v2/status without creating a database record
        ↓
Successful test issues a short-lived signed registration proof
        ↓
Register Instance becomes available
        ↓
Any form change invalidates the proof and disables Register Instance
        ↓
Registration verifies the proof and repeats the reachability probe
        ↓
Only a successful recheck may create the instance
```

The proof is bound to the authenticated user and a fingerprint of the submitted
form. It contains no raw endpoint, password, bearer token, or other submitted
value. The proof expires after ten minutes. Test success and failure are shown
through persistent operational toast notifications and written to Activity
Audit Log; the form does not render duplicate inline success or error panels.

Connection testing and Full Validation are separate contracts:

- **Test Connection** verifies configuration completeness, endpoint
  reachability, authentication, TLS negotiation, and `/api/v2/status`.
- **Register Instance** persists the reusable connection identity only after a
  successful test and defensive pre-save recheck.
- **Full Validation** runs from the saved instance workspace and establishes
  capabilities, compatibility profile, readiness, and diagnostic evidence.
- **Scope Binding** controls where the validated connection is eligible for
  primary, secondary, or fallback resolution.

## Validation diagnostics contract

The **Validation & Capabilities** workspace is the technical source of truth for
what KAORI observed and what an operator must change when a capability is not
available. Every capability definition includes:

- the API request or payload inspection used as evidence;
- explicit success criteria;
- required connection, proxy, authentication, TLS, or alert-payload setup;
- operational impact when the capability is missing;
- ordered remediation steps; and
- the dependent KAORI operational domains affected by the result.

API capability checks treat a successful HTTP 2xx JSON response as valid even
when the returned collection is empty. Metadata capabilities are sample-based:
when there are no representative active alerts or silences, metadata may be
reported as **Not observed**. Operators should create or trigger controlled
representative data, rerun Full Validation, and remove temporary test objects
when the evidence has been collected.

When the documented external success criteria pass but KAORI still reports a
missing capability, treat the issue as an adapter/probe mismatch. Capture only a
sanitized response shape, compare it with `app/alertmanager/probes.py` and the
provider-neutral normalizer, adjust capability discovery without adding
product-specific UI branches, and add a regression fixture before revalidation.

The technical workflow is:

```text
Run Full Validation
        ↓
Review required capability failures
        ↓
Apply endpoint / authentication / TLS / proxy / payload fixes
        ↓
Rerun Full Validation
        ↓
Review operational-domain readiness
        ↓
Refresh Runtime
        ↓
Confirm Effective Source Resolution
```

## Runtime health and history contract

Runtime health is separate from validation readiness. Readiness describes the
saved connection and capability contract. Runtime health describes the latest
observed operational condition.

The health score is a weighted result of connectivity, readiness, provider API,
capability discovery, and latency factors. The UI interprets the score as:

```text
0–59   critical
60–84  attention required
85–100 healthy
```

The runtime workspace uses a compact two-domain layout. **Health Interpretation**
combines the score, semantic posture, threshold bar, and weighted factors in one
operator card. **Diagnostic Pipeline** presents ordered checks as a technical
sequence with evidence, duration, and remediation guidance without reserving
unused vertical space.

Runtime history uses the global KAORI pagination contract: default `5`
observations with `5`, `10`, `25`, and `50` as supported page sizes. KAORI keeps
a rolling maximum of **100 observations per provider instance**. The observation
write and removal of records beyond that limit occur in the same transaction.

## Scope binding contract

Scope binding creation uses HTMX and updates the Scope & Resolution workspace
without a full-page reload. Every create, rejection, and unexpected failure
produces a persistent notification, toast feedback, and Activity Audit Log
record.

Binding validation rules are explicit:

- scope type and canonical scope key are required;
- a managed-cluster scope must reference an existing KAORI cluster;
- one Alertmanager instance cannot be bound to the same scope more than once;
- only one enabled primary Alertmanager source is allowed for one scope;
- priority must be between `1` and `1000`; lower values are preferred within the
  same source role; and
- duplicate submissions are rejected as **already exists** rather than silently
  updating the existing binding.

The create form does not act as an implicit edit form. To replace an existing
mapping, remove the current binding through the confirmation modal and create
the replacement with the intended role and priority. This keeps lifecycle and
audit semantics explicit.

## Runtime flows

### Register and bind a source

```text
Administrator completes the registration form
        ↓
Test Connection succeeds and unlocks registration
        ↓
KAORI rechecks reachability and stores the connection identity
        ↓
Readiness becomes validation_required
        ↓
Administrator runs Full Validation
        ↓
KAORI discovers version and API capabilities
        ↓
Administrator adds one or more scope bindings
        ↓
Bound consumers may resolve the source
```

A binding is not required when an instance is first registered. This allows a
standalone source to be validated before an asset scope is assigned.

### Resolve alerts for an asset

```text
Consumer requests alerts for scope_type + scope_key
        ↓
Binding resolver orders primary / secondary / fallback sources
        ↓
Reader selects the first enabled and usable source
        ↓
AlertmanagerClient calls /api/v2/alerts
        ↓
Generic normalizer produces canonical provider records
        ↓
Consumer domain enriches and interprets the records
```

If a source fails, the consumer facade may try the next bound source. Provider
fallback is separate from cross-source deduplication or alert correlation;
those remain analytics/intelligence responsibilities.

### Kubernetes compatibility flow

Existing Kubernetes Analytics continues to call:

```python
get_alertmanager_status(cluster_id=...)
get_alertmanager_alerts(cluster_id=...)
get_alertmanager_silences(cluster_id=...)
```

Those functions are compatibility facades. Internally they resolve a
`kubernetes_cluster` binding first and only use the legacy cluster configuration
as a temporary fallback. Kubernetes Analytics does not instantiate the HTTP
client or query Alertmanager configuration tables directly.

## File ownership

| File | Responsibility | Boundary |
|---|---|---|
| `README.md` | Defines purpose, architecture, model boundary, file ownership, compatibility, migration, and remaining work. | Update whenever files or responsibilities change. |
| `__init__.py` | Package marker only. | No registration, network calls, or persistence side effects. |
| `contracts.py` | Pure provider-neutral dataclasses for connection specifications, queries, validation results, and canonical alert records. | Must not import Flask request state or SQLAlchemy models. |
| `client.py` | Low-level Alertmanager API v2 HTTP client: authentication headers, bounded requests, JSON parsing, status, alerts, silences, and transport error mapping. | No database access, UI context, audit feedback, or asset enrichment. |
| `exceptions.py` | Alertmanager connection, authentication, and response exception hierarchy. | Preserve specific failure categories at integration boundaries. |
| `forms.py` | Parses and validates instance and binding input, normalizes endpoints, bounds timeouts/priorities, and preserves omitted credentials. | Input contract only; no database or network operations. |
| `repository.py` | Query-only persistence access for instances, bindings, scope resolution, and the legacy model. | No commits, HTTP calls, or presentation formatting. |
| `client_factory.py` | Converts an instance or legacy configuration into a connection specification and `AlertmanagerClient`. | Centralizes credential and transport construction. |
| `status.py` | Persists sanitized runtime status and validation health fields for instance or legacy sources. | No UI rendering or provider reads. |
| `sanitization.py` | Removes user info, query strings, and fragments from endpoints before presentation or operator-console links. | Pure security utility; it does not modify the stored connection endpoint. |
| `validation.py` | Executes status, alerts, and silences probes; discovers version/capability profiles; classifies failure; persists readiness. | One validation use case, no route branching. |
| `reader.py` | Performs runtime status, alert, and silence reads against one already resolved source. | Returns normalized provider data; does not resolve asset bindings. |
| `bindings.py` | Creates, deletes, and resolves scope bindings; rejects duplicate instance-to-scope mappings and enforces one primary source per scope. | Owns binding rules, not asset-domain enrichment. |
| `resolver.py` | Ranks bound sources by required capabilities, readiness, runtime health, role, and priority, and emits a deterministic decision trace. | Pure selection logic over persisted state; no HTTP requests or cross-source deduplication. |
| `consumer.py` | Public scope-based consumer facade with source ordering, readiness gating, fallback, and Kubernetes scope compatibility. | Preferred entry point for all bound operational consumer domains. |
| `service.py` | Stable application facade for instance lifecycle, validation, bindings, legacy redirects, and existing cluster-based function signatures. | Routes and consumers should use this facade instead of internal modules. |
| `presentation.py` | Builds sanitized instance inventory/detail contexts, binding labels, pagination, filters, and UI status summaries. | Must never expose credentials or raw URL query strings. |
| `registration.py` | Issues and verifies short-lived, user-bound registration proofs for successfully tested draft forms. | Tokens contain only a signed form fingerprint and never raw credentials or submitted connection values. |
| `notifications.py` | Creates persistent toast and Activity Audit feedback for instance, validation, binding, and lifecycle operations. | Metadata must be sanitized and secret-free. |
| `routes.py` | Thin HTTP orchestration for instance create/edit/delete, validation, binding management, and legacy cluster redirects. | Permission checks and response selection only; business rules remain in services. |
| `metrics.py` | Deprecated compatibility wrapper for previous alert-normalization imports. | Do not add behavior; migrate imports to `normalizers/`. |
| `normalizers/__init__.py` | Exposes the supported generic normalization API. | No asset-specific behavior. |
| `normalizers/alerts.py` | Converts raw API v2 alert payloads to canonical provider dictionaries, including labels, annotations, severity, state, timestamps, receiver, fingerprint, and source identity. | No Kubernetes resource classification. |
| `normalizers/silences.py` | Normalizes generic Alertmanager silence records and matcher payloads. | Domain interpretation remains with consumers. |
| `normalizers/time.py` | Safe Alertmanager timestamp parsing and duration helpers. | Pure utility module. |

## HTTP and UI ownership

Canonical routes:

```text
GET  /integrations/alertmanager
GET  /integrations/alertmanager/instances/new
POST /integrations/alertmanager/instances/test-connection
POST /integrations/alertmanager/instances/new
GET  /integrations/alertmanager/instances/<instance_id>
POST /integrations/alertmanager/instances/<instance_id>
POST /integrations/alertmanager/instances/<instance_id>/validate
POST /integrations/alertmanager/instances/<instance_id>/bindings
POST /integrations/alertmanager/instances/<instance_id>/bindings/<binding_id>/delete
POST /integrations/alertmanager/instances/<instance_id>/delete
```

Legacy cluster routes remain as compatibility redirects:

```text
/integrations/alertmanager/cluster/<cluster_id>
/integrations/alertmanager/cluster/<cluster_id>/test
```

The canonical inventory presents instances, not clusters. Cluster Management may
show a compact binding summary and link into the integration domain, but it does
not own Alertmanager configuration.

### Instance Manage presentation contract

The Configuration tab follows the shared KAORI workspace hierarchy:

```text
Peer Workspace Summary Cards
↓
Primary Configuration Form     Configuration Flow
                               Connection Type Guide
                               Related Alert Intelligence Workspace
```

Connection Contract, Change Impact, and Integration Flow are peer summaries and
therefore use the same Violet Workspace Summary Card. Configuration Flow is the
primary ordered workflow for the tab and uses the shared Info Flow component even
though it is placed in the right-side column. Connection Type Guide remains
non-sequential, while navigation to Alert Intelligence remains isolated in the
Related Page Card. A generic page-context card is not used because the active tab,
form sections, and summaries already establish the page responsibility.

## Security rules

- Never render password, bearer token, authorization header, CA material, raw
  validation response, or URL query string.
- Endpoint input must use HTTP/HTTPS, include a hostname, use a base path rather than `/api/v2`, and must not embed credentials, query parameters, or fragments.
- Blank credential input on edit means preserve the existing credential.
- Changing authentication mode clears credentials that no longer apply.
- TLS verification defaults to enabled.
- All network operations use bounded timeout values.
- Authentication failures are not retried as transport failures.
- Activity Audit metadata may include instance identity, deployment type,
  capability status, response time, and sanitized failure class only.
- The current database columns still store credentials directly. Production
  hardening must replace them with encrypted-at-rest values or references to a
  protected secret provider before broad multi-tenant adoption.

## Refactor assessment after this foundation change

| Area | Current status | Next action |
|---|---|---|
| Provider client | Cohesive and read-only. | Add injectable session/retry policy only when required. |
| Instance and binding persistence | Implemented. | Remove the legacy table after a compatibility release. |
| Service decomposition | Implemented into repository, factory, validation, reader, binding, consumer, presentation, and notification modules. | Keep `service.py` as a facade; do not move responsibilities back into it. |
| Generic normalization | Implemented. | Move remaining consumer-side Kubernetes normalization during Analytics refactor. |
| Integration inventory/configuration | Instance-first and binding-aware. | Add first-class selectors as Server, HCI, and Storage registries are introduced. |
| Credential storage | Still direct database text. | High-priority security hardening. |
| Scheduled validation | Manual validation implemented. | Add Celery validation scheduling and cooldown/circuit state later. |
| Analytics consumer boundary | Existing Kubernetes Analytics uses compatibility facade. | Next project: split the large Kubernetes alert analytics service. |

## Non-negotiable maintenance rules

1. Do not add `cluster_id` ownership back to provider instances.
2. Do not create separate Alertmanager HTTP adapters for Kubernetes, Server,
   HCI, or Storage.
3. Do not add asset-specific branching to generic normalizers.
4. Do not let analytics import `AlertmanagerClient`, repositories, or database
   configuration models directly.
5. Do not delete the legacy model until migration, route, and external import
   compatibility have been verified in a release.
6. Keep all SQLAlchemy models in `app/models/`.
7. Keep Alertmanager authoritative for routing, inhibition, silences, receivers,
   and notification delivery.

## Compatibility and Capability Validation

Alertmanager validation follows the same architectural principle used by the Prometheus integration, but probes APIs and observed alert metadata rather than Prometheus metric names.

The validation layers are:

1. **Connectivity and status** — endpoint, authentication, TLS, response time, and `/api/v2/status`.
2. **Provider API capability** — readable Alerts API and Silences API.
3. **Observed payload capability** — labels, `alertname`, severity, fingerprint, timestamps, receiver, annotations, runbook URL, generator URL, and silence matchers.
4. **Compatibility profile** — maps the detected runtime version to a versioned profile under `app/alertmanager/profiles/`.
5. **KAORI module readiness** — evaluates which KAORI features are ready, degraded, or unavailable from the observed capabilities.

Runtime consumers must check capability keys instead of comparing version strings. Adding support for another Alertmanager runtime line should primarily require a new profile module, not branching throughout services or analytics.

### Compatibility files

| File | Responsibility |
|---|---|
| `capabilities.py` | Canonical provider and payload capability catalog. |
| `probes.py` | Discovers metadata capabilities from sampled alerts and silences. Empty data means metadata is not observed, not necessarily unsupported. |
| `requirements.py` | Maps capability requirements to KAORI modules such as Alert Inventory, Kubernetes Alerts, Alert Intelligence, Recommendations, and Runbook Integration. |
| `profiles/base.py` | Immutable profile contract. |
| `profiles/alertmanager_v025.py` | Legacy Alertmanager 0.25–0.26 profile and known limitations. |
| `profiles/alertmanager_v033.py` | Current Alertmanager 0.27–0.33 profile. |
| `profiles/__init__.py` | Profile registry and version resolver. |
| `validation.py` | Executes API probes, discovers payload capabilities, resolves profiles, evaluates module readiness, and persists the verified capability set. |

Capability discovery is evidence-based. When Alertmanager currently has no active alerts, KAORI can verify the Alerts API but cannot claim that optional metadata such as `runbook_url` or `receiver_metadata` was observed. The UI therefore shows **Not observed** rather than treating every absent optional field as an integration failure.

## Capability-aware source resolution

`resolver.py` is the selection boundary between asset consumers and bound Alertmanager instances. Consumers provide a scope and the capabilities needed for the operation. The resolver evaluates every enabled binding using:

1. required capability availability;
2. persisted readiness state;
3. latest runtime health;
4. binding role (`primary`, `secondary`, `fallback`);
5. configured priority.

A healthy secondary source is preferred over an unhealthy primary source. A source that was positively validated and exposes the requested capabilities is preferred over a source whose capability state has not yet been observed. Instances migrated before capability probing remain selectable as `unknown` during the compatibility window, but rank below positively verified sources.

The resolver does not execute HTTP requests and does not perform cross-source alert deduplication. It produces a deterministic ordered candidate list and a decision trace. `consumer.py` attempts candidates in that order and records whether runtime fallback was used.

New asset analytics must call the consumer facade or `resolve_alertmanager_sources()`; they must not query `AlertmanagerBinding`, inspect credentials, or instantiate the provider client directly.

## Effective source resolution presentation

The instance detail page exposes the resolver decision for every bound scope. Alert retrieval and silence retrieval are evaluated independently because they require different capabilities (`alerts_v2` and `silences_v2`). The presentation layer shows the effective instance, current-instance participation, role, priority, operational state, eligibility, missing capabilities, and the resolver decision reason for every candidate. This is diagnostic presentation only; source selection remains owned by `resolver.py` and provider execution/fallback remains owned by `consumer.py`.

## Shared integration runtime adapter

`runtime_adapter.py` implements the provider-neutral Integration Runtime contract. It translates Alertmanager validation output and persisted instance observations into diagnostics, weighted health factors, a capability snapshot, and a runtime state. The HTMX runtime refresh endpoint updates only the runtime panel and records a sanitized audit event. Alertmanager-specific HTTP and capability logic stays in this package; health contracts and scoring remain under `app/integrations/runtime/` for reuse by Prometheus and other integration providers.


## Simplified source-selection flow

Primary, secondary, and fallback bindings define preference, not simultaneous
alert processing.

```text
Consumer asks for alerts or silences
        ↓
Resolver checks the required capability and current runtime state
        ↓
Use the healthiest eligible source
        ↓
If the live request fails, try the next eligible source
```

Example:

```text
Primary is healthy and has Alerts API
→ use Primary for alerts

Primary has no Silences API
Secondary has Silences API
→ use Secondary for silences

Primary becomes unreachable during the request
→ consumer tries Secondary
```

Kubernetes Analytics never implements this decision. It calls the public
consumer facade and receives canonical Alertmanager records.

## Shared Integration Runtime relationship

Alertmanager is the first provider adapter for the shared framework documented
in `docs/architecture/integration-runtime.md`. Alertmanager owns endpoint,
authentication, API probing, profile mapping, and provider diagnostics. The
shared framework owns runtime contracts, readiness-versus-health vocabulary,
health scoring, refresh orchestration, and template-safe presentation.

The complete cross-domain standards are listed in
`docs/architecture/README.md` and must be reviewed before adding another
provider or changing consumer behavior.

## Runtime observation history

The Alertmanager instance detail page renders the shared runtime observation
history after the live runtime panel. The table defaults to 5 records and supports
5, 10, 25, and 50 through HTMX pagination. The summary and page-size selector are
kept together on the left side of the standard KAORI Violet pagination footer.

A manual runtime refresh persists a new observation and updates both the runtime
panel and the history section in the same HTMX response. Rows show health, score,
latency, trigger source, capability snapshot, recovery/degradation transitions,
and capability drift. KAORI retains the latest 100 records for this Alertmanager
instance and deletes older records during the next successful runtime write.
Retained records remain append-only presentation evidence; resolver ordering and
consumer fallback remain unchanged.

## KAORI Violet semantic presentation contract

Alertmanager is part of the first semantic-color rollout together with Prometheus.

- Primary Violet is used only for KAORI identity, active navigation, primary actions, focus state, and selected state.
- Operational status uses the matching Normal, Info, Warning, Critical, or Neutral family.
- Status and metadata labels are compact, rectangular, and borderless. Border-reference colors are retained for semantic panels, callouts, confirmation dialogs, and destructive controls.
- Alertmanager templates use the application sans-serif family for endpoints, scope keys, identifiers, and runtime evidence. Monospace remains limited to dedicated code or payload contexts.
- Landing, registration, instance detail, validation, runtime history, scope binding, and effective-source resolution must remain inside the shared `kaori-integration-semantic` presentation scope.



### Global semantic color contract

This workspace consumes the shared KAORI palette and label components. Provider templates must not introduce a separate status palette. Pending maps to Info, maintenance to Warning, and disabled/unknown to Neutral.
