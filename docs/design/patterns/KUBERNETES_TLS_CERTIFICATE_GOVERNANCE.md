# Kubernetes TLS Certificate Governance

## Purpose

TLS Certificate Governance is a read-oriented registry for certificate validity, declared-host coverage, Ingress relationships, collection evidence, and controlled rotation handoff.

## Governance Overview landing contract

Kubernetes Governance Overview is the capability-first landing page for implemented Kubernetes governance controls. TLS Certificates is the first implemented capability; future capabilities join the same Overview grammar only after implementation and authorization. The Overview must not advertise placeholder workflows.

`governance.view` authorizes the landing page. Detailed TLS counts, snapshot evidence, and TLS drill-down are resolved only when the current user also has `tls_certificates.view`. A user without that permission sees the implemented TLS capability in a restricted state but receives no certificate counts or collection evidence.

Normal Governance Overview reads committed KAORI database/worker evidence only. It never queries Kubernetes at request time and never owns mutation. Kubernetes remains authoritative for live resource state; controlled TLS mutation remains owned by Kubernetes Secret Operations.

Canonical Overview hierarchy:

```text
Hero
Governance Scope
└── Governance Capabilities
Committed Governance Posture        # only when TLS evidence is authorized
├── TLS Governance Snapshot
└── TLS Governance Posture
Governance Model
└── Provider Authority / Committed Evidence / Controlled Mutation
```

## Canonical structure

```text
Compact Hero
TLS Collection Snapshot
TLS Inventory Operations
Certificate Posture — shared Section Intro
└── Certificate Validity
Certificate Inventory — shared Section Intro
└── TLS Certificate Registry
Detail Style 2 — Full Workspace Modal
```

This is the first canonical **Governance Resource Registry** implementation.

## Cluster setup blocker

Governance Overview and TLS Certificate Governance use the same Kubernetes setup-blocked Hero right-panel contract as Dashboard, Inventory, and Kubernetes Operations. When no cluster is registered, the Hero remains visible, the right panel switches to `Governance Readiness / Cluster Setup Required`, and the detailed cluster-registration guidance stays in the onboarding banner below it. TLS snapshot, posture, registry, and mutation handoff evidence are not presented as zero-valued operational evidence while setup is blocked.

## Evidence authorities

| Evidence | Authority |
|---|---|
| TLS Secret certificate metadata | Kubernetes TLS Secret collection |
| Declared hosts and Ingress consumers | Kubernetes Ingress collection |
| Validity state | KAORI global validity policy |
| Rotation mutation | Kubernetes Secret Operations |
| Sync dispatch and outcome | KAORI Jobs and Activity Audit |

A missing Ingress consumer is not equivalent to a successful collection with zero consumers. Secret collection and Ingress mapping maintain separate evidence states.

## Global validity policy

Defaults:

```text
Renewal Window  30 days
Critical Window 7 days
```

The values are configured with:

```text
TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS
TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS
```

Expiry uses the exact `not_after` timestamp. A certificate with less than 24 hours remaining is still valid and belongs to the Critical Window; it is not Expired until `not_after <= now`.

Validity labels:

```text
Valid
Renewal Window
Critical Window
Expired
Invalid
Unknown
```

## Declared-host coverage

Coverage compares current certificate SAN/Common Name identities with declared Ingress TLS hosts from the same collected scope.

```text
Fully Covered
Partial
Uncovered
No Declared Hosts
Not Reported
```

Coverage is declaration evidence, not live endpoint reachability. Host values remain Technical Values. Opening a declared host is an explicit action and never proves route availability.

Wildcard identities use single-label semantics. `*.example.com` covers `api.example.com`, but it does not cover `example.com` or `deep.api.example.com`. KAORI must not broaden wildcard coverage across multiple DNS labels.

## Section hierarchy and cluster-source action

TLS Governance reuses `components/section_intro.html` for the plain hierarchy above certificate posture and registry content. The component adds no card geometry or separate palette.

Cluster-source navigation is labeled **Open Cluster Integrations** and routes to `integrations.kubernetes`, matching Kubernetes Inventory.

## Compact registry table

```text
Certificate
Scope
Validity
Host Coverage
Ingress Usage
Details
```

The table directly opens the shared Full Workspace Modal. It does not render an intermediate expanded row. The dedicated detail route remains a direct-link and no-JavaScript fallback.

## Full Workspace Modal

Canonical content:

```text
Certificate Summary
Certificate Identity
Issuer & Validity
Technical Identifiers
Host Coverage
Ingress Consumers
Collection Evidence
Host Coverage Matrix
Certificate Identities
Governance Snapshot Boundary
Rotation Handoff
```

The modal uses permission-aware rotation actions. Governance never owns the mutation form.

The modal header follows the shared Full Workspace Modal alignment contract: lifecycle/status labels sit below the descriptive line and align with the title/description text column, never with the outer-left icon edge.

## TLS Inventory Operations and certificate posture

TLS inventory synchronization is a standalone operational surface immediately after the TLS Collection Snapshot. Its placement and interaction follow the same background-inventory pattern used by Kubernetes Tenant:

```text
Collection Snapshot
→ Inventory Operations
→ Evidence Posture
→ Registry
```

`TLS Inventory Operations` owns Sync TLS, Configure Sync, Bulk Rotation handoff, worker progress, automatic policy state, last successful collection, and next scheduled execution. It must not be nested inside certificate validity metrics.

Certificate validity remains a separate evidence block under the shared `Certificate Posture` section intro. `Certificate Inventory` is the outer section context for `TLS Certificate Registry`; the outer and inner titles intentionally express different hierarchy levels.

Accepted background sync dispatch remains inline and does not create a queued/completion toast or unread Notification Deck item. Terminal worker evidence persists the Notification Deck result and triggers navigation refresh without a full-page reload.

## Single TLS rotation workspace

Single TLS rotation is intentionally full width. The old sticky right context rail is retired for this workflow because it created visual imbalance after the main content evolved. The canonical order is:

```text
Target TLS Secret
Replacement Certificate Pair & Validation
Controlled Rotation & Governance Posture
```

`Target TLS Secret` uses one compact three-column identity strip (Cluster, Namespace, Secret), followed by a bounded Current TLS Posture header, a four-metric evidence grid, and a dedicated Issuer/Fingerprint technical row. The previous split target/posture columns are retired because they create unused vertical space and constrain long fingerprints. `Replacement Certificate Pair & Validation` owns both upload cards, file-processing guardrails, validation result, and the embedded Validate/Update action bar. `Controlled Rotation & Governance Posture` keeps the four-step mutation flow full-width, then places TLS Governance state, Days Remaining, Host Coverage, and the Certificate Details handoff in one compact horizontal evidence strip. A large flow/posture side-panel split, page-local right rail, separate validation action card, or standalone posture accordion must not return.

TLS Certificate Detail uses `data-kaori-tls-detail-layout="evidence-workspace-v2"` for both the Full Workspace Modal and direct-link page content. The layout is intentionally limited to three primary sections: `Certificate Identity & Validity`, `Coverage & Consumer Evidence`, and `Collection & Governance`. Certificate detail must not return to independent nested `detail_card` stacks for identity, validity, coverage, collection, and rotation handoff; those concerns are grouped into structured evidence grids and one Governance footer so the workspace stays dense and readable.

### Rotation file-picker stability

Single and bulk TLS rotation use explicit chooser buttons that invoke hidden native file inputs. The native file input must not be `sr-only` or be the focus target of an enclosing upload-card label, because returning from the operating-system file picker can scroll the document to that off-screen control. KAORI restores focus to the visible chooser with `preventScroll: true` and keeps the current viewport stable.

## Collection evidence

Per cluster:

```text
Secret Collection
Ingress Mapping
```

Supported states:

```text
Collected
Permission Unavailable
API Unavailable
Collection Failed
Not Reported
```

The Snapshot Context Bar aggregates missing or failed evidence for the active scope.

## Permission ownership

Governance owns:

```text
tls_certificates.view
tls_certificates.sync
```

Secret Operations owns:

```text
kubernetes_secrets.rotate_tls
kubernetes_secrets.bulk_rotate_tls
```

TLS mutation authority uses only `kubernetes_secrets.rotate_tls` and `kubernetes_secrets.bulk_rotate_tls`. The retired Governance mutation permission keys are removed from the registry and existing assignments are migrated to the canonical permissions.

## Data-minimization contract

The Kubernetes API response is processed transiently by the collector. KAORI may read and decode only `tls.crt` for certificate metadata extraction. It must not access, decode, log, persist, notify, or audit `tls.key` or unrelated Secret values.

## Pagination and filtering

- filter events are scoped to the filter form;
- the Rows selector refreshes `#tls-certificates-page-workspace` using `outerHTML`;
- page size defaults to 5 and offers 5/10/25/50;
- Previous, numeric pages, and Next preserve all active filters and use the same HTMX target and loading indicator.
## Toast and Notification Deck policy

- TLS inventory sync uses `JobExecution` as the active-progress authority. Dispatch acknowledgement is transient; terminal success, partial success, cancellation, and failure persist to Notification Deck and Activity Audit.
- The worker must persist terminal delivery evidence before marking the job terminal. `result_summary_json` records `activity_audit_saved` and the requester IDs whose Notification Deck row was persisted.
- TLS Secret validation remains transient. Single and bulk rotation terminal outcomes are persistent regardless of status.
- Notification payloads contain only safe certificate metadata and counts; certificate bytes, private keys, Secret values, raw exceptions, and provider payload dumps are prohibited.
- Toast labels may state **Activity Audit** or **Notification Deck** only when the corresponding persistence was confirmed.
- User-facing notification and execution titles preserve canonical acronyms and Title Case. The registered sync display name is **TLS Certificate Sync**; generic snake-case `.title()` reconstruction is not used for registered job names.

## Final release contract

### Authorization before readiness

Governance readiness or clusterless handling must never short-circuit route authorization. The canonical order is:

```text
request
  ↓
permission_required
  ↓
cluster/schema readiness
  ↓
read or dispatch
  ↓
render / operational feedback
```

`governance_bp.before_request` must not own clusterless responses. TLS read/status/sync paths evaluate their readiness only after `tls_certificates.view` or `tls_certificates.sync` has admitted the request.

### Hero right-side standard

Governance uses only approved KAORI Hero right accessories:

- Governance Overview: **Context Icon Box** through the canonical Hero context header.
- TLS Certificate Registry: **Status Badge Box** inside the canonical status-oriented Hero context card.

No page-local fourth Hero accessory type is permitted.

### L0–L7 release evidence

The release boundary requires Static Quality, Contract, Unit, Functional, Integration, Security Regression, Rendering/UI Contract, and End-to-End Smoke evidence. Kubernetes/provider reachability remains an Integration/worker responsibility; the E2E smoke validates Flask/session/templates/application shell deterministically without requiring a live cluster.
