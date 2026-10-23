# Kubernetes TLS Certificate Governance

## Purpose

TLS Certificate Governance is a read-oriented registry for certificate validity, declared-host coverage, Ingress relationships, collection evidence, and controlled rotation handoff.

## Governance Overview landing contract

Kubernetes Governance Overview is the **domain-first** landing page for Kubernetes governance as a whole. TLS Certificates is the first implemented child capability; it does not define the Hero, Hero context, primary posture, or information architecture of the Governance domain. Future implemented governance capabilities join the same catalog without redesigning Overview. Placeholder capability links are prohibited.

`governance.view` authorizes the landing page. `tls_certificates.view` controls only whether the TLS Certificates child capability can be opened. Governance Overview does **not** load TLS certificate inventory, certificate counts, TLS snapshot posture, or other child-capability detail evidence solely to render the domain landing page.

The ready-state Hero represents the generic Kubernetes governance boundary: Kubernetes is authoritative for live resource/enforcement state, KAORI owns normalized governance evidence and orchestration, and the canonical Hero action is **Open Cluster Integrations**. Overview itself remains read-only and issues no live Kubernetes request.

Canonical Overview hierarchy:

```text
Hero — Kubernetes Governance / Overview
Governance Scope
└── Governance Capabilities
    └── TLS Certificates                  # current implemented child capability
Governance Model
└── Governance Operating Model
    ├── Provider Authority
    ├── Policy & Guardrails
    ├── Committed Evidence
    └── Controlled Handoffs
```

Detailed TLS posture, validity, coverage, collection evidence, and rotation context remain owned by the TLS Certificates capability page.

The Overview Hero uses the compact KAORI description **Review Kubernetes governance controls, evidence, and ownership.** The Governance Operating Model keeps policy copy compact: **KAORI applies governance policy and authorization guardrails without cloning the provider control plane.**

Governance Capabilities is a scalable equal-height catalog. The parent section owns no TLS-specific action. Each implemented capability contributes one self-contained card with identity, status, purpose, boundary, permission state, and its own action. The catalog uses an auto-fitting minimum-width grid so one capability fills the available row, multiple capabilities distribute evenly, and adding another implemented governance capability does not require changing the surrounding Overview composition. Unimplemented capabilities are never rendered as placeholders.

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

### DevContainer table-width and evidence-copy refinement (#733)

The six-column fixed registry prioritizes long technical identifiers and declared-host coverage:
**Certificate 27%, Scope 22%, Validity 12%, Host Coverage 20%, Ingress Usage 9%, Details 10%**.
Preserve existing responsive behavior without horizontal scroll: Host Coverage is shown at
`lg` and above, and Ingress Usage at `xl` and above. Keep the shared details
modal, full hover values, keyboard-accessible headings, filters, and pagination.

Validity keeps the policy-derived status badge and factual expiry date; day text is
compact (`74 days left` / `3 days expired`) without changing calculations.
The `No Declared Hosts` badge is not repeated underneath when host declarations
are factually absent. If coverage collection is unavailable, show `Not Reported`
and `Coverage evidence unavailable`. If hosts exist, display the covered/declared
ratio and only show uncovered-count support when nonzero.

Ingress Usage shows the observed Ingress count, adding declared-host counts only when
nonzero; unavailable Ingress mapping remains `Not Reported` plus `Ingress mapping
unavailable`, never an invented zero. Full details and evidence distinctions remain
accessible. Presentation changes do not infer live TLS reachability or trust.

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


## TLS rotation target identity and freshness admission (#1306)

An approved rotation must preserve the selected committed target identity:
the Kubernetes TLS Secret UID collected with its namespace/name must match
the live UID read before PATCH. Unknown or malformed UID evidence, or
deletion/recreation at the same namespace/name, fails closed until TLS
synchronization refreshes inventory. Live Secret type, resourceVersion,
dry-run and Secret-value scrubbing remain mandatory.

Ingress coverage admission requires both Secret and Ingress source status
Collected. Both cluster collection-state collected_at and certificate-row
collected_at must fall within the existing TLS sync job-policy interval plus
its established freshness grace. This proves qualified recent committed
evidence, not live Ingress reachability. Preview and server-side single/bulk
apply use the same fail-closed policy; any blocked bulk target prevents every
provider PATCH. No new UI state or break-glass override is introduced.

## Bounded TLS inventory reconciliation (#1325)

Worker-side collection is bounded and payload-scrubbed before reconciliation.
A completed Secret scan reconciles existing TLS inventory in 100-identity ORM
batches instead of loading all historical cluster rows into application memory.
Each successfully collected record receives one committed scan-generation
timestamp; stale records from **only that cluster** are pruned by a scoped SQL
DELETE where their generation does not match. Collection-state and inventory
changes share the same database transaction/commit, including successful
zero-certificate scans. Duplicate Secret identities abort and roll back the
reconciliation rather than silently replacing or pruning evidence. Fatal or
incomplete Secret collection never enters reconciliation or prunes existing
rows. Preserve immutable Secret UID/source provenance across updates.

This reduces ORM materialization but is **not** a benchmark PASS. Verify
bounded per-batch memory, PostgreSQL query plan/latency and transactional
no-prune failure paths in Dev Container before official admission.

## Provenance-safe TLS collection freshness (#1327)

`TLSCertificateCollectionState.updated_at` means the latest collection attempt;
`collected_at` advances only after a complete successful Secret collection.
Failed attempts may update source status and error detail, but they do not
refresh the committed certificate evidence clock or delete the old certificate
snapshot. Ingress mapping remains an independently qualified evidence source.

The TLS Operations `Last Successful` indicator is derived from committed
certificate-row `collected_at` and collection-state `collected_at` **only
when the Secret source is Collected**. If the prior successful collection
contained zero TLS Secrets and a subsequent attempt failed, the bounded
`JobExecution` history can supply a last-successful timestamp **only for
that specific target cluster** when a successful or partially successful
job explicitly lists the cluster and does not list it among failures.
No fleet-level job success automatically qualifies a failed cluster. Never choose a newer failed attempt's
`updated_at` or failed collection-state timestamp, nor treat a fleet job's
partial success as success for each target cluster. A fleet scope is `Current`
only if **every registered cluster** has a non-stale successful Secret snapshot
and Collected Ingress mapping. Exceptions take precedence over Current; the
underlying last-known-good timestamp remains visible and must not imply current
mapping evidence. The legacy database column's meaning is clarified in-place;
no new schema or UI taxonomy is introduced.


## As-of-now committed certificate validity (#1326)

The committed `not_after`, parse result, certificate identity, and collection
timestamp remain source facts. Every read derives current validity against the
same configured critical/renewal windows without writing ORM fields or asking
Kubernetes. SQL CASE supplies a consistent filter, severity sort, summary and
pagination classification. Python `classify_certificate_validity` supplies
matching row/detail/rotation presentation and current days remaining.
Persisted Invalid/Unknown statuses take precedence over timestamp inference.
Exact expiry uses `not_after <= evaluated_at`; `collected_at` and posture
`validity_evaluated_at` are separate so reassessment never implies new data.
