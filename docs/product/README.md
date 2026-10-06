# KAORI Platform Direction

This document is the canonical product-direction reference for KAORI. Review it before changing platform wording, navigation, page scope, feature boundaries, integration architecture, or long-term roadmap decisions.

Implementation-specific documents may add technical detail, but they must not redefine the platform positioning described here.

## 1. Platform Positioning

KAORI is an extensible infrastructure operations platform that provides unified visibility, operational control, analytics, reporting, governance, and administration across integrated infrastructure assets and data sources.

KAORI is not positioned as a product-specific dashboard or a collection of pages for one infrastructure technology. New integrations must extend the platform through consistent capability and domain contracts without changing the global KAORI identity.

Recommended platform-level description:

> KAORI provides unified infrastructure visibility, operational workflows, analytics, reporting, and governance to support reliable day-to-day operations and proactive infrastructure management.

## 2. Capability Domains

### 2.1 Compute and Infrastructure Assets

KAORI provides a common operational layer for compute and runtime infrastructure integrated into the platform.

The platform-level experience must use global terms such as **infrastructure assets**, **compute environments**, **runtime environments**, or **integrated infrastructure**. Technology-specific names belong only in implementation, configuration, inventory, and domain-detail pages where the source scope must be explicit.

This domain is expected to expand as additional infrastructure tools and platforms are integrated.

### 2.2 Storage Integration

KAORI will provide visibility and operational context for storage services integrated into the platform.

The initial direction is object-storage integration through an S3-compatible interface. Platform-level descriptions must remain implementation-neutral. Specific software, endpoint configuration, credentials, bucket behavior, retention rules, and deployment choices belong in the related integration and implementation documentation.

### 2.3 Infrastructure Mapping

KAORI will provide visual mapping to help users understand how infrastructure assets are connected and where operational risk may propagate.

The mapping capability includes:

- asset connectivity and relationship views;
- dependency mapping between infrastructure components and workloads;
- service or resource impact paths; and
- risk mapping based on health, capacity, configuration, lifecycle, and dependency context.

Mapping must be built from normalized inventory and relationship data. It must not fabricate dependencies when the source data is incomplete.

### 2.4 Asset Inventory

KAORI maintains normalized inventory for every supported infrastructure integration.

Inventory provides identity, ownership, environment, lifecycle, status, relationship, and snapshot context for downstream dashboards, analytics, operations, mapping, governance, and reports.

Each integration owns its collection and normalization adapter. KAORI owns the unified inventory contract and user experience.

### 2.5 Operational Analytics

KAORI transforms infrastructure data into operational insight that supports day-to-day readiness and proactive management.

The analytics direction includes:

- utilization and operational posture;
- capacity analysis and capacity planning;
- trend, forecast, and growth-risk analysis;
- prioritized findings and recommendations;
- anomaly and risk context; and
- proactive readiness before service degradation or resource exhaustion occurs.

Analytics must clearly identify scope, source, freshness, and unavailable states. Recommendations must be evidence-based and linked to impacted assets and remediation guidance.

### 2.6 Centralized Operational Activities

KAORI may provide selected infrastructure operation workflows when centralization improves consistency, safety, auditability, and operator efficiency.

Operational workflows must follow these rules:

- explicit asset and environment scope;
- permission enforcement on the server side;
- validation before mutation;
- clear impact and dependency context;
- user-visible success or failure state;
- activity and audit recording without sensitive payload exposure; and
- separation between read-only visibility and infrastructure-changing actions.

KAORI should not add an operation merely because an integrated source exposes an API. The workflow must provide operational value beyond opening the source tool directly.

### 2.7 Reporting and Historical Context

KAORI provides historical and management-ready reporting for infrastructure operations.

Reporting includes:

- generated operational and management reports;
- historical snapshots and trend context;
- scheduled and on-demand generation;
- report templates and controlled customization;
- retention, archive, verification, and cleanup lifecycle; and
- readable summaries for both technical and non-technical audiences.

Reports must preserve data scope, source status, generation time, and relevant limitations.

### 2.8 Administration, Governance, and Audit

KAORI provides the administrative foundation required to operate the platform safely.

This direction includes:

- user management;
- roles, permissions, and access control;
- system and integration configuration;
- authentication and account controls;
- notification and operational activity records;
- audit, retention, archive, and lifecycle controls; and
- additional governance capabilities introduced as operational requirements evolve.

UI visibility is never a substitute for server-side authorization.

## 3. Product and Integration Principles

### Capability-first, not product-first

Global pages, menus, descriptions, and reports describe the operational capability. Technology or software names are used only where users need to configure, identify, filter, or troubleshoot a specific integration.

### Integration through explicit adapters

Each source integration must have an explicit adapter, source-of-truth contract, health state, normalization boundary, and permission model. Source-specific behavior must not leak into unrelated domains.

### Unified experience, domain-specific ownership

KAORI should share navigation patterns, design primitives, filters, pagination, audit behavior, and error handling. Data collection, operations, and business rules remain owned by the relevant domain.

### Visibility before mutation

Read-only inventory, mapping, analytics, and impact context should be available before operational write actions are introduced. Mutation workflows require stronger validation, permissions, safeguards, and audit coverage.

### Honest operational state

Unavailable, unsupported, stale, partial, or planned capabilities must be shown explicitly. KAORI must not generate estimated health, relationships, recommendations, or readiness states without sufficient evidence.

### Extensible by design

New infrastructure categories and integrations should be added without renaming the platform, creating a second global navigation model, or rewriting shared product positioning.

## 4. Capability Maturity Labels

Use these labels consistently in planning and review documents:

- **Available** — implemented, accessible, and supported in the current application.
- **In progress** — actively being implemented but not yet a complete operational contract.
- **Planned** — approved direction with a defined purpose but not implemented.
- **Future** — valid platform direction that still requires discovery and prioritization.

Do not present planned or future capability as currently available.

## 5. Wording Contract

### Preferred global wording

- infrastructure operations platform;
- unified infrastructure visibility;
- integrated infrastructure assets;
- operational analytics and readiness;
- centralized operational workflows;
- dependency and risk mapping;
- management-ready reporting; and
- governance, administration, and audit.

### Avoid at platform level

- positioning KAORI as a dashboard for one technology;
- listing current integrations as the definition of KAORI;
- naming a vendor or software product in the main platform description;
- describing a source tool as a KAORI feature when KAORI only consumes its data;
- claiming proactive or intelligent behavior without evidence and operational context; and
- presenting roadmap items as implemented functionality.

Technology-specific wording remains valid on integration setup, domain inventory, operational workflow, troubleshooting, and implementation documentation pages.

## 6. Page Review Contract

Every KAORI page review must verify:

1. **Purpose** — the page has one clear operational responsibility.
2. **Scope** — asset, environment, integration, and time scope are explicit.
3. **Source** — the data source and freshness contract are known.
4. **Capability state** — available and planned behavior are not mixed.
5. **Action boundary** — visibility, recommendation, approval, and mutation are separated appropriately.
6. **Impact context** — operational changes show affected assets or dependencies when available.
7. **Authorization** — route and action permissions are enforced server-side.
8. **Auditability** — meaningful operations produce safe activity and notification records.
9. **Extensibility** — the page does not hard-code a global platform concept to one integration.
10. **Wording** — user-facing descriptions communicate function rather than promoting a product or implementation choice.

## 7. Documentation Hierarchy

Use this documentation order when making changes:

1. `docs/product/README.md` — canonical KAORI positioning, capability direction, and wording rules.
2. `docs/architecture/` — cross-domain architecture and module standards.
3. `app/<domain>/README.md` — domain-specific source-of-truth, security, workflow, and extension rules.
4. Implementation files — code, templates, migrations, tests, and configuration.

When a feature changes product direction or architecture, update the relevant README in the same patch.

## 8. Platform Boundary

KAORI integrates with infrastructure systems and data sources; it does not need to replace every source platform, collector, monitoring engine, configuration system, or infrastructure manager.

KAORI adds value by normalizing infrastructure context, connecting assets and dependencies, producing operational insight, centralizing selected workflows, enforcing governance, preserving history, and presenting information consistently across integrations.
