# KAORI Operational Data Semantics & Presentation Standard — Design

**Status:** Approved product semantics; implementation pending  
**Date:** 2026-08-25  
**Scope:** All KAORI operational domains and future integrations  
**Applies to:** Kubernetes, Object Storage, Server, HCI, GitOps, Registry, Backup, Secrets, Policy, and future asset/operations integrations

## 1. Purpose

KAORI must present operational data consistently across Dashboard, Inventory, Analytics, Intelligence, and Alert Intelligence. The same words — especially *alert*, *anomaly*, and *recommendation* — must not mean different things on different domain pages.

This standard defines:

- the authoritative purpose of each product surface;
- which data source each surface may consume;
- how provider alerts differ from KAORI alert cases;
- how contextual Analytics recommendations differ from durable Intelligence recommendations;
- what Dashboard may summarize;
- what Inventory must never infer;
- the promotion path from evidence to Intelligence and Alert Intelligence;
- the presentation contract future integrations must follow.

The goal is a stable semantic foundation that remains valid as KAORI adds more integrations.

## 2. Product-semantic layers

The layer numbers below describe **product meaning**, not dependency direction. Dashboard is Layer 2 in the product model but is a downstream consumer of Inventory, Analytics, and Intelligence outputs.

### Layer 1 — Inventory: Asset Truth

**Question answered:** What assets exist, and what factual state did KAORI last commit for them?

Inventory is a factual, snapshot-backed asset authority.

Allowed content:

- identity and technical metadata;
- object configuration captured by inventory;
- resource relationships;
- factual capacity values captured by inventory;
- lifecycle state that exists directly on the asset, such as `Ready`, `Running`, `Bound`, `Expired`, or `Phase`;
- labels, namespaces, owners, versions, and similar factual metadata;
- last-collected or snapshot timestamps.

Prohibited content:

- Intelligence recommendations;
- Analytics recommendations;
- Alert Intelligence cases;
- provider-alert interpretation;
- forecast conclusions;
- anomaly conclusions;
- inferred operational risk labels that do not exist in the inventory source.

Examples:

- `Restarts: 12` is valid inventory evidence.
- `High Restart Risk` is not Inventory; it belongs to Analytics or Intelligence.
- `Bucket Usage: 8.4 TiB` is valid if committed by Inventory.
- `Projected Capacity Exhaustion` is not Inventory.

### Layer 2 — Dashboard: KAORI Operational Summary

**Question answered:** What does KAORI currently consider operationally important for this selected domain or asset?

Dashboard is a summary consumer. It does not become a raw provider viewer and does not independently evaluate durable rules.

Canonical Dashboard content:

1. operational posture;
2. concise asset/capacity summary;
3. analytics-derived KPI summaries;
4. **Alert Insight** from KAORI Alert Intelligence cases;
5. **Recommended Actions** from central Intelligence recommendations, maximum five actionable findings;
6. data freshness and source readiness.

Dashboard must not count raw Prometheus/Alertmanager alerts directly as Dashboard alerts.

#### Dashboard Alert Insight contract

Every operational Dashboard uses the same semantic presentation:

```text
Alert Insight

Total        Highest        Source
18           Critical       Alert Intelligence

[KAORI Alert Cases Available]   [KAORI Alert Intelligence]
```

Rules:

- `Total` = active KAORI `AlertCase` count in selected scope;
- `Highest` = highest severity among active KAORI AlertCases;
- `Source` = literal presentation label `Alert Intelligence`;
- first metadata label = `KAORI Alert Cases Available` when cases are available;
- second metadata label = `KAORI Alert Intelligence`;
- do not use domain-specific alternatives such as `Top 3 Cases`;
- source text must remain readable on one line when space permits and must wrap rather than ellipsize when constrained.

#### Dashboard Recommended Actions contract

`Recommended Actions` always consumes **central Intelligence Recommendations**:

```text
Central Intelligence Recommendations
        ↓
selected domain + selected asset
        ↓
actionable / active findings
        ↓
priority ranking
        ↓
maximum 5
```

Dashboard must not construct Recommended Actions directly from local Capacity, Forecast, Top Consumer, or other Dashboard snapshot calculations.

### Layer 3 — Analytics: Evidence Analysis & Operational Interpretation

**Question answered:** What does the selected operational evidence show for this scope and observation window?

Analytics owns operational analysis over committed metrics/provider evidence. It is context-aware and time-window aware.

Analytics may consume:

- committed metrics-worker snapshots;
- Prometheus or another Metrics Source evidence captured by the worker;
- Alertmanager/provider alert evidence;
- forecast-worker snapshots;
- inventory fallback only where the field contract explicitly allows it;
- domain-specific operational evidence.

Analytics may derive:

- utilization/headroom/pressure;
- request and error posture;
- trends;
- forecast projections;
- anomaly signals;
- contextual Analytics recommendations.

Analytics does not own durable Intelligence finding lifecycle.

#### Analytics Overview contract

Analytics Overview is a summary surface and must not use a generic central `Recommendations` tab.

Where alert evidence exists, Overview uses an **Alerts** tab that summarizes:

- provider alerts from Alertmanager or provider-specific alert source;
- Metrics Source `ALERTS` fallback where that domain supports it;
- KAORI-derived anomaly-signal summary;
- navigation to the domain `Alerts & Anomalies` workspace for full evidence.

For Kubernetes and Object Storage, this Overview Alert model must be conceptually aligned.

#### Contextual Analytics Recommendation contract

A non-Overview Analytics page may expose a local `Recommendations` tab when it can derive actionable guidance from the **current page evidence**.

These recommendations are:

- contextual to the current workspace;
- scoped to the selected asset/system/cluster;
- scoped to the selected observation window when relevant;
- derived from that Analytics payload;
- non-durable;
- not central Intelligence Recommendation records;
- not Alert Intelligence cases.

Examples:

**Kubernetes Capacity** recommendations derive from capacity/headroom/request/limit evidence.  
**Object Storage Capacity & Usage** recommendations derive from usage/headroom/quota/growth evidence.  
**Object Storage Performance** recommendations derive from request errors, waiting requests, inflight work, node availability, and throughput evidence.  
**Forecast** recommendations derive from history quality, growth, projection, and threshold ETA.  
**Top Consumers** recommendations derive from concentration, contribution, pressure, and consumer-level evidence.

A contextual Analytics Recommendation must never be implemented as merely "central Intelligence findings filtered by category". That is a different semantic object.

#### Alerts & Anomalies contract

`Alerts & Anomalies` is an operational evidence surface with three distinct concepts:

1. **Provider Alerts** — alert lifecycle evidence from Alertmanager/provider alert source, with Metrics Source fallback only where defined;
2. **Anomaly Signals** — abnormal conditions KAORI derives from committed operational evidence;
3. **Recommendations** — contextual response guidance derived from the alerts/anomalies evidence shown in that Analytics workspace.

This page is not Alert Intelligence and does not own case lifecycle.

### Layer 4 — Intelligence: Durable Decision & Action Layer

**Question answered:** Which durable findings has KAORI identified, how important are they, and what should operators do about them?

Intelligence owns durable rule-driven findings.

An **Intelligence Recommendation** has durable semantics such as:

- stable recommendation/finding identity;
- rule ownership;
- domain and affected assets;
- severity;
- source/provider identity;
- evidence;
- remediation guidance;
- lifecycle state;
- governance/audit metadata;
- eligibility for promotion into an AlertCase.

Intelligence Recommendation is different from Analytics Recommendation:

| Property | Analytics Recommendation | Intelligence Recommendation |
| --- | --- | --- |
| Owner | Analytics workspace | Intelligence rule engine |
| Scope | Current page/scope/window | Durable domain/asset finding |
| Persistence | Contextual/non-durable | Durable |
| Lifecycle | None | Yes |
| Severity | Optional presentation priority | Canonical finding severity |
| Dashboard Recommended Actions | No | Yes, top actionable findings |
| AlertCase promotion | No direct promotion | Eligible by policy |

### Layer 5 — Promotion & Presentation Contract

Layer 5 defines how evidence becomes durable operational state and how consumers present it.

#### Canonical terms

**Provider Alert**  
Alert originating from Alertmanager or another monitoring provider.

**Anomaly Signal**  
Abnormal condition derived by KAORI from committed operational evidence.

**Analytics Recommendation**  
Contextual, page-specific guidance derived from current Analytics evidence.

**Intelligence Recommendation**  
Durable, rule-owned Intelligence finding with lifecycle and remediation semantics.

**KAORI AlertCase**  
Durable operational case managed by Alert Intelligence.

Do not use the unqualified word `alert` in code or presentation when the source can be ambiguous. Prefer the canonical terms above.

#### Current promotion flow

The current durable case flow is:

```text
Intelligence Recommendation
        ↓ promotion policy
KAORI AlertCase
        ↓
Alert Intelligence
        ↓
Dashboard Alert Insight
```

Provider Alerts currently remain Analytics evidence unless a separate normalization/promotion contract explicitly promotes them into Alert Intelligence in a future release.

Future provider-origin promotion may be added as:

```text
Provider Alert
    ↓ normalization
    ↓ promotion policy
KAORI AlertCase
```

Dashboard does not change when future promotion sources are introduced because Dashboard consumes Alert Intelligence cases, not provider alerts directly.

## 3. Canonical data-flow model

```text
External Providers / Platform APIs
        │
        ├──────────────────────────────────────────────┐
        │                                              │
        ▼                                              ▼
Inventory Collectors                           Metrics / Alert Providers
        │                                              │
        ▼                                              ▼
Committed Inventory Snapshot                  Committed Analytics Evidence
        │                                              │
        │                                         ┌────┴───────────────┐
        │                                         │                    │
        │                                         ▼                    ▼
        │                                  Provider Alerts        Anomaly Signals
        │                                         │                    │
        │                                         └────────┬───────────┘
        │                                                  ▼
        │                                      Contextual Analytics
        │                                        Recommendations
        │
        └──────────────────────┐
                               │
                               ▼
                        Intelligence Rules
                               │
                               ▼
                    Durable Intelligence Findings
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
          Dashboard Recommended      Promotion Policy
               Actions                    │
            (max 5)                       ▼
                                  KAORI AlertCase
                                         │
                                         ▼
                                  Alert Intelligence
                                         │
                                         ▼
                                  Dashboard Alert Insight
```

## 4. Source-authority matrix

| Surface | Primary authority | Allowed fallback | Must not masquerade as |
| --- | --- | --- | --- |
| Inventory | Committed inventory/discovery snapshot | None unless inventory contract defines provider-specific fallback | Analytics, Intelligence, Alert Intelligence |
| Dashboard KPI summary | Canonical Dashboard aggregation over committed Inventory/Analytics summaries | Explicit documented fallback only | Raw provider viewer |
| Dashboard Alert Insight | Alert Intelligence AlertCases | None | Provider Alerts |
| Dashboard Recommended Actions | Central Intelligence Recommendations | None | Analytics Recommendations |
| Analytics Overview Alerts | Provider alert evidence + anomaly summary | Metrics Source/provider fallback where explicitly defined | Alert Intelligence |
| Analytics page Recommendations | Current Analytics page evidence | Explicit field-level data fallback only | Intelligence Recommendations |
| Alerts & Anomalies Provider Alerts | Alertmanager/provider alert source | Metrics Source `ALERTS` where defined | AlertCase |
| Alerts & Anomalies Anomaly Signals | KAORI Analytics derivation | None | Provider Alert |
| Intelligence Recommendations | Intelligence rules/findings | Imported provider findings only through defined Intelligence contracts | Contextual Analytics guidance |
| Alert Intelligence | Durable AlertCases | Future normalized promotion sources by policy | Raw provider alert list |

## 5. Domain application rules

Every operational domain added to KAORI must declare the following before release:

1. **Inventory authority** — what committed asset snapshot represents factual truth;
2. **Analytics evidence authority** — which committed worker/provider evidence is analyzed;
3. **Provider-alert authority** — which provider owns raw alert lifecycle evidence;
4. **Anomaly derivation** — which abnormal conditions KAORI derives from Analytics evidence;
5. **Contextual recommendation builders** — which Analytics workspaces provide local recommendations and from which evidence;
6. **Intelligence rule ownership** — which durable findings exist for the domain;
7. **AlertCase promotion policy** — which durable findings/provider events may become AlertCases;
8. **Dashboard contract** — how KPIs, Alert Insight, and top five Recommended Actions are summarized;
9. **fallback boundaries** — every permitted fallback must be field-specific and visible in presentation/source labels;
10. **RBAC boundary** — each surface remains permission-scoped and cannot expose protected data through cross-surface reuse.

A domain is not release-complete until these ten declarations are represented in tests or canonical architecture documentation.

## 6. Kubernetes target contract

### Inventory

Remains factual Kubernetes asset snapshot only.

### Dashboard

- Alert Insight consumes Kubernetes-scoped KAORI AlertCases;
- Recommended Actions consumes top five actionable central Intelligence Recommendations for the selected cluster;
- source presentation uses `Alert Intelligence` plus `KAORI Alert Cases Available` and `KAORI Alert Intelligence` metadata labels;
- raw Alertmanager/Metrics Source alert counts do not become Dashboard alert counts.

### Analytics

- Overview contains Alerts summary sourced from Provider Alerts + anomaly signals;
- Capacity, Utilization, Storage, Workload, Forecast, and Top Consumers keep their page-specific contextual recommendation builders;
- Alerts & Anomalies separates Provider Alerts, Anomaly Signals, and contextual Recommendations.

## 7. Object Storage target contract

### Inventory

Remains factual Object Storage asset snapshot only.

### Dashboard

- Alert Insight consumes Object Storage-scoped KAORI AlertCases;
- Recommended Actions consumes top five actionable central Intelligence Recommendations for the selected Object Storage system;
- local Dashboard capacity/forecast/top-consumer calculations must not manufacture durable Recommended Actions.

### Analytics Overview

The Overview `Recommendations` tab is replaced by **Alerts**.

The Alerts tab summarizes:

- Object Storage Provider Alerts from Alertmanager-first evidence;
- Metrics Source `ALERTS` fallback where the binding supports it;
- KAORI Object Storage anomaly-signal summary;
- link to full `Alerts & Anomalies` evidence.

### Analytics contextual recommendations

Object Storage contextual tabs must mirror Kubernetes semantics while using Object Storage-specific evidence:

- Capacity & Usage → capacity/headroom/quota/growth recommendations;
- Performance → request/error/queue/inflight/node-availability/throughput recommendations;
- Forecast → history/growth/projection/threshold-ETA recommendations;
- Top Consumers → concentration/contribution/pressure/bucket-consumer recommendations;
- Alerts & Anomalies → response recommendations derived from provider alerts and anomaly signals.

These builders remain in Object Storage Analytics and do not query central Intelligence Recommendations.

## 8. Presentation and naming rules

### Alert labels

Use:

- `Provider Alerts`
- `Anomaly Signals`
- `KAORI Alert Cases`
- `Alert Intelligence`

Avoid ambiguous labels such as `Alerts` when multiple concepts are shown in the same workspace.

### Recommendation labels

Use:

- `Recommendations` inside an Analytics page only when the context clearly indicates the workspace;
- `Recommended Actions` on Dashboard for central Intelligence top-five findings;
- `Recommendations` in Intelligence for durable Intelligence findings.

Supporting copy must make ownership clear where context is not obvious.

### Source labels

Compact summary metrics use short source values, for example:

- `Alert Intelligence`
- `Alertmanager`
- `Metrics Source`
- `Inventory`
- `Forecast Worker`

Long provenance is expressed by metadata labels or supporting text, not by truncating the source value.

## 9. Dependency and ownership rules

Expected ownership direction:

```text
Inventory route/service → Inventory snapshot/repository
Analytics route/service → Analytics snapshot + domain analytics builders
Intelligence route/service → durable Intelligence findings/rules
Alert Intelligence → durable AlertCase lifecycle
Dashboard service → read-only summary interfaces from Analytics + Intelligence + Alert Intelligence
```

Prohibited dependency patterns:

- Inventory importing Intelligence recommendation builders;
- Analytics importing central Intelligence recommendations for local contextual recommendation tabs;
- Dashboard querying Alertmanager directly for Alert Insight;
- Dashboard manufacturing Intelligence Recommended Actions from local snapshot heuristics;
- Alert Intelligence serving as raw Alertmanager list UI;
- Intelligence silently replacing missing evidence with unrelated sources.

## 10. Failure and unknown semantics

Missing evidence remains `Unknown` and must never silently become zero, healthy, or no-alert.

Rules:

- missing Provider Alert evidence means provider-alert state is unavailable, not `0 alerts`;
- missing Analytics capacity does not become zero utilization;
- missing Intelligence findings means no finding record was produced, not proof that the asset is healthy;
- missing AlertCase evidence means Alert Insight readiness must reflect unavailable/unknown state where applicable;
- every fallback is explicit and field-specific.

## 11. Loading and progress presentation boundary

Loading state and execution progress are separate concepts.

- canonical table/HTMX loading uses the shared KAORI loading bar contract;
- Notification Deck job progress uses a fixed full-width track with proportional fill based on the actual progress percentage;
- different fill lengths are expected when job progress differs;
- progress bars must not be normalized to equal visual length because that would misrepresent job state;
- tests should lock track geometry, not force equal fill percentages.

## 12. Security, RBAC, and audit

Cross-surface reuse must not bypass authorization.

- Dashboard aggregation must enforce the same domain/asset permissions required by its source surface;
- Inventory permissions do not imply access to Intelligence findings;
- Analytics access does not imply Alert Intelligence case access;
- mutation/elevation paths remain owned by Intelligence/Automation Control, never Analytics tabs;
- AlertCase promotion and lifecycle transitions remain auditable;
- Dashboard and Analytics remain read-only operational consumers unless an explicit governed action opens a separate review/execution flow.

## 13. Testing contract

### Architecture/contract tests

Tests must assert durable semantic boundaries, including:

- Inventory pages do not render Recommendation/Alert Intelligence interpretation;
- Dashboard Alert Insight consumes Alert Intelligence cases;
- Dashboard Recommended Actions use central Intelligence Recommendations and enforce max five;
- Analytics Overview Alert tab consumes provider-alert/anomaly evidence;
- contextual Analytics Recommendations do not import central Intelligence Recommendation readers;
- Alerts & Anomalies separates provider alerts from anomaly signals;
- source labels identify the correct authority;
- Object Storage and Kubernetes implement the same product semantics even when their evidence differs.

### Runtime tests

Runtime coverage should prove:

- no source-readiness failure is rendered as healthy/zero;
- RBAC remains enforced on cross-surface consumption;
- selected asset/system and time-window state survive Analytics tab changes;
- Dashboard counts match Alert Intelligence case scope;
- Dashboard Recommended Actions are capped at five and ranked deterministically;
- contextual recommendation builders change when their source Analytics evidence changes.

### UI contracts

UI tests should verify:

- canonical `Alert Insight` labels and source presentation;
- no ellipsis on short source values such as `Alert Intelligence`;
- Overview uses `Alerts`, not central `Recommendations`, where specified;
- contextual recommendation tab labels and page ownership remain consistent;
- loading/progress geometry follows the canonical shared components.

## 14. Migration plan

### Phase A — Canonical standard and contracts

- register this semantic standard in KAORI architecture/engineering review documentation;
- add cross-domain contract tests for the semantic matrix;
- add canonical helper names/typed contracts where needed.

### Phase B — Dashboard alignment

- normalize Kubernetes and Object Storage `Alert Insight` presentation;
- normalize Dashboard Recommended Actions to central Intelligence findings, max five;
- remove domain-specific alternative labels such as `Top 3 Cases`;
- preserve source/freshness evidence separately from Alert Insight.

### Phase C — Object Storage Analytics alignment

- replace Overview `Recommendations` with `Alerts`;
- implement Object Storage-local contextual recommendation builders per Analytics workspace;
- remove central Intelligence Recommendation dependency from Object Storage Analytics contextual tabs;
- preserve `Alerts & Anomalies` as provider-alert + anomaly evidence workspace.

### Phase D — Regression repair

- restore canonical stacked loading geometry for affected Kubernetes Analytics record tables;
- restore embedded Active Alert/Anomaly record table surfaces;
- restore HTMX auto-filter behavior for Object Storage Analytics bucket tables;
- restore Top Consumer wording contract;
- fix Ruff formatter drift and Pyright-safe compatibility redirects.

### Phase E — Future integration template

Every new operational domain must adopt the ten domain declarations in section 5 and add contract coverage before release-surface registration.

## 15. Acceptance criteria

This design is fully implemented when:

1. Inventory is factual-only across Kubernetes and Object Storage;
2. Dashboard Alert Insight is sourced only from KAORI AlertCases;
3. Dashboard Recommended Actions use central Intelligence Recommendations, maximum five;
4. Kubernetes and Object Storage Alert Insight use the same labels and metadata contract;
5. Analytics Overview uses Provider Alert + Anomaly summaries rather than central Recommendations;
6. Object Storage Analytics contextual Recommendations are locally derived from page evidence, like Kubernetes Analytics;
7. Alerts & Anomalies distinguishes Provider Alerts, Anomaly Signals, and contextual Recommendations;
8. Intelligence Recommendations remain durable rule-owned findings;
9. provider alert fallback and missing-evidence semantics remain explicit;
10. static quality, Pyright, architecture, code-health, contract, runtime, and final-release gates pass without increasing debt baselines.

## 16. Non-goals

This standard does not, by itself:

- add provider-origin AlertCase promotion;
- change Alertmanager routing/inhibition behavior;
- create new Automation Control execution semantics;
- redefine Inventory collection strategy;
- make Analytics recommendations durable records;
- merge Analytics and Intelligence recommendation engines;
- expose raw provider APIs directly from Dashboard web requests.

## 17. Decision summary

KAORI will use the following permanent semantic model:

```text
Inventory = asset truth
Dashboard = KAORI operational summary
Analytics = operational evidence analysis + contextual recommendations
Intelligence = durable rule-owned findings and recommended actions
Alert Intelligence = durable KAORI AlertCase lifecycle
```

Provider Alerts, Anomaly Signals, Analytics Recommendations, Intelligence Recommendations, and KAORI AlertCases are separate first-class concepts and must remain separately named, sourced, tested, and presented.
