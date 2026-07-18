# Alertmanager Integration

## Purpose

`app/alertmanager` is KAORI's integration adapter for connecting to Alertmanager
instances that already exist outside KAORI. The integration may ultimately point
to either:

- an Alertmanager deployed for one Kubernetes cluster;
- a shared or standalone Alertmanager serving multiple Kubernetes clusters; or
- another externally managed Alertmanager instance that KAORI is authorized to
  observe.

Alertmanager remains the authoritative alert routing, grouping, inhibition, and
silence engine. KAORI does not replace Alertmanager. KAORI uses the integration
to discover readiness, retrieve alert and silence data, normalize the provider
payload, centralize visibility, and supply downstream operational analytics and
intelligence.

The current implementation is read-oriented. It calls Alertmanager API v2 for
status, alerts, and silences. It does not currently create silences, modify
routing configuration, or manage Alertmanager lifecycle.

## Compatibility contracts

Alertmanager uses two separate compatibility contracts:

- Endpoint/API profile: `alertmanager-api-v2-legacy` or
  `alertmanager-api-v2-current`.
- Capability profile: `alert-management-v1`.

Version detection is automatic. KAORI validates:

- `/api/v2/status`;
- `/api/v2/alerts`; and
- `/api/v2/silences`.

API v1 is never used. The endpoint profile represents runtime/API
compatibility. The capability profile represents the alert-management behavior
required by Kubernetes Alerts & Anomalies, Alert Intelligence, silence
visibility, and routing posture.

## Current architecture boundary

The package owns the Alertmanager-specific integration contract:

```text
Alertmanager endpoint
        ↓
app/alertmanager/client.py
        ↓
API/version/capability validation
        ↓
provider payload normalization
        ↓
consumer domains such as Kubernetes alert analytics
```

The package must remain separate from Kubernetes interpretation. Generic
Alertmanager concerns belong here; Kubernetes-specific resource recognition,
enrichment, and operational scoring belong in the Kubernetes analytics bounded
context.

### Current implementation limitation

The current persistence model is keyed directly by `cluster_id` through
`app/models/alertmanager.py`. That means the implementation currently supports
one cluster-associated configuration, not a first-class standalone/shared
Alertmanager instance.

This differs from the intended product scope. Supporting a standalone or shared
Alertmanager requires an instance-first model and explicit asset bindings. The
models must remain centralized under `app/models/` in accordance with KAORI's
model ownership rule.

Recommended future model boundary:

```text
AlertmanagerInstance
├── endpoint and authentication
├── compatibility/readiness state
├── detected version and capabilities
└── operational metadata

AlertmanagerBinding
├── alertmanager_instance_id
├── asset_type
├── asset_id
└── binding purpose / priority
```

This structure allows one Alertmanager instance to serve multiple clusters and
allows future asset domains to bind to their own Alertmanager instances without
copying the provider adapter.

## Runtime flows

### Configuration and validation

```text
Administrator selects an integration target
        ↓
Form values are parsed and normalized
        ↓
Configuration is persisted
        ↓
Readiness becomes validation_required
        ↓
KAORI calls /api/v2/status
        ↓
KAORI probes alerts and silences capabilities
        ↓
Version/profile/readiness are persisted
        ↓
Toast and Activity Audit Log record the operation
```

### Runtime alert retrieval

```text
Consumer requests alerts for a bound asset
        ↓
KAORI resolves the Alertmanager configuration
        ↓
Readiness gate is checked
        ↓
AlertmanagerClient calls /api/v2/alerts
        ↓
Generic payload normalization is applied
        ↓
Asset-specific analytics enriches the normalized alert
```

### Runtime silence retrieval

```text
Consumer requests silence context
        ↓
KAORI resolves the Alertmanager configuration
        ↓
AlertmanagerClient calls /api/v2/silences
        ↓
Raw silence payload is returned to the consuming domain
        ↓
The consuming domain evaluates matchers and operational impact
```

## File ownership

| File | Responsibility | Notes and boundaries |
|---|---|---|
| `README.md` | Defines the package purpose, file ownership, provider boundary, compatibility contract, and refactor direction. | Keep this document synchronized whenever files are added, removed, renamed, or assigned a new responsibility. |
| `__init__.py` | Marks `app.alertmanager` as a Python package. | It intentionally contains no runtime registration or side effects. Blueprint registration remains explicit in the application factory. |
| `client.py` | Implements the low-level Alertmanager HTTP API v2 client. It builds authentication headers, performs GET requests, classifies HTTP/transport failures, parses JSON, and exposes status, alerts, silences, and connection-test operations. | This file must remain provider/API focused. It must not contain database access, Flask request handling, Kubernetes enrichment, UI context construction, or Activity Audit behavior. |
| `exceptions.py` | Defines the Alertmanager exception hierarchy used to distinguish connection, authentication, and response failures. | Consumers should catch `AlertmanagerError` at integration boundaries and preserve the specific subtype for diagnostics. |
| `forms.py` | Parses and normalizes Alertmanager configuration submitted by the UI. It owns endpoint normalization, supported authentication mode validation, optional credential cleanup, timeout bounds, and checkbox parsing. | This is a parsing contract, not a persistence or connectivity service. It currently uses a frozen dataclass rather than WTForms. |
| `metrics.py` | Normalizes raw Alertmanager alert payloads into KAORI dictionaries, including severity, state, timestamps, duration, receiver, labels, annotations, runbook URL, and fingerprint. It also currently detects Kubernetes-style resource labels. | The filename is misleading because the file does not process metrics. Generic normalization should be renamed or moved to `normalizers/alerts.py`; Kubernetes resource detection must move to the Kubernetes alert analytics domain. |
| `routes.py` | Exposes the cluster-scoped Alertmanager configuration and connection-test HTTP endpoints. It handles permission checks, form submission, redirects/HTMX responses, operational feedback, and rendering. | Routes should remain thin. The current route functions contain workflow orchestration and repeated feedback construction that should move into use-case and presentation modules. |
| `service.py` | Coordinates configuration persistence, client creation, connection/capability validation, readiness/status updates, runtime alert retrieval, silence retrieval, and configuration-page context. | This file currently mixes repository, validation, runtime reader, status persistence, and presentation-context responsibilities and should be split. |

## External model and consumer ownership

The package uses models that remain centralized outside this folder:

- `app/models/alertmanager.py` owns persisted Alertmanager configuration and
  readiness fields.
- `app/models/cluster.py` currently owns the one-to-one cluster relationship.

Primary consumers include:

- `app/integrations/` for inventory and configuration visibility;
- Kubernetes alert analytics for alert, silence, source-health, and routing
  context; and
- future Alert Intelligence workflows that consume normalized provider data.

Consumers must not instantiate HTTP requests directly. They must call the
Alertmanager integration service or a future explicit reader interface.

## Security and data-handling rules

- Never render raw credentials, authorization headers, or TLS traces in inline
  UI errors.
- Store low-level diagnostics only in controlled logs or Activity Audit metadata
  that does not contain secrets.
- Authentication fields must be cleared when the selected authentication type no
  longer uses them.
- The current model stores basic-auth passwords and bearer tokens directly in
  database text columns. Before production-grade multi-instance expansion,
  replace direct secret storage with an encrypted-at-rest field or a protected
  secret reference.
- Connection validation must use bounded connect/read timeouts.
- TLS verification must default to enabled.
- Runtime consumers must respect compatibility/readiness state and must not query
  an integration marked `validation_required` or `blocked`.

## Refactor review

The review is based on current file size, function size, responsibility count,
and coupling—not line count alone.

| File | Current size | Review | Priority |
|---|---:|---|---|
| `client.py` | ~252 lines, one 236-line class | Cohesive enough for the current read-only API surface. Split only when retries, certificate material, proxies, write operations, or multiple transports are introduced. Prefer injecting a `requests.Session` before adding more request behavior. | Medium / later |
| `forms.py` | ~154 lines | Small and cohesive. No split required. Add field-level validation errors if the UI needs richer feedback. | Low |
| `metrics.py` | ~417 lines; `normalize_alertmanager_alert()` ~122 lines | Responsibility and naming are no longer clean. It mixes generic Alertmanager normalization, time formatting, receiver parsing, and Kubernetes resource detection. | High |
| `routes.py` | ~315 lines; route functions ~177 and ~90 lines | Too much application workflow, repeated Activity Audit payload construction, and response branching inside HTTP handlers. | High |
| `service.py` | ~450 lines; connection validation ~137 lines | Mixes persistence, factory, validation, health state, runtime retrieval, and page context. This makes testing and standalone-instance migration harder. | High |
| `exceptions.py` | ~14 lines | Clear and appropriately small. | None |

### Recommended target package

```text
app/alertmanager/
├── README.md
├── __init__.py
├── client.py                 # API v2 transport only
├── exceptions.py
├── forms.py                  # input parsing
├── repository.py             # Alertmanager instance/config persistence
├── client_factory.py         # config -> client
├── validation.py             # status/capability/profile validation
├── reader.py                 # alerts and silences runtime reads
├── status.py                 # readiness and last-check persistence
├── normalizers/
│   ├── __init__.py
│   ├── alerts.py             # provider-neutral alert normalization
│   └── time.py               # provider timestamp/duration helpers
├── presentation.py           # integration page context and feedback payloads
└── routes.py                 # thin HTTP adapter
```

Kubernetes-specific label-to-resource resolution must not remain in this target
package. It belongs in the Kubernetes alert analytics enrichment layer.

## Refactor sequence

1. Add tests that freeze the current status, alert, silence, and validation
   contracts.
2. Extract generic alert normalization from `metrics.py`; move Kubernetes
   resource detection to Kubernetes alert enrichment.
3. Extract repository and client-factory behavior from `service.py` without
   changing routes.
4. Extract validation and runtime reader services.
5. Move Activity Audit/toast payload construction out of `routes.py` and leave
   routes responsible only for HTTP input/output.
6. Introduce instance-first Alertmanager persistence plus asset bindings in a
   dedicated migration.
7. Preserve current cluster-scoped URLs as compatibility redirects while the UI
   migrates to instance and binding management.

Do not combine the package split and the persistence-model migration in one
change. Each phase needs independent tests and rollback capability.

## Non-goals

`app/alertmanager` must not:

- replace Alertmanager routing, grouping, inhibition, or notification delivery;
- become a Kubernetes analytics service;
- calculate incident readiness or ownership scores;
- own cross-asset alert correlation;
- hide provider failures by silently returning healthy state; or
- place SQLAlchemy models inside the integration package.
