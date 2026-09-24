# KAORI Page Archetype and Navigation Registry

**Parent authority:** #572  
**Workstream:** #606  
**Status:** Design System v2 composition-selection authority

## Purpose

This registry determines which existing KAORI page grammar and navigation family an implementation should compose. It does not introduce a new visual system, new templates, or page-local geometry.

Detailed visual and interaction rules remain owned by:

- `KAORI_DESIGN_SYSTEM.md`;
- `KAORI_STYLING_GUIDE.md`;
- reusable component contracts under `docs/design/components/`;
- reusable page-pattern contracts under `docs/design/patterns/`;
- owning module specifications for domain behavior.

The selection rule is:

```text
Operator intent
→ one primary page archetype
→ existing pattern/component authority
→ domain composition
```

A page may embed components associated with another archetype, but it still has one primary page intent. A local visual hybrid is not a new archetype.

## Classification Rules

1. Classify the page by the operator's primary intent, not by route name or provider.
2. Select one primary archetype from this registry before choosing local composition.
3. Reuse the existing detailed pattern/component owner for geometry, typography, state, and responsive behavior.
4. Provider-specific nouns, evidence, actions, and permissions may vary; the page grammar does not.
5. If an active page cannot be classified without inventing local geometry, record a bounded design-system gap before implementation.
6. Do not redesign an accepted page merely to make examples visually identical.

## Archetype Registry

| Archetype | Primary operator intent | Canonical composition | Hero / action posture | Production references |
| --- | --- | --- | --- | --- |
| **Landing** | Discover KAORI capabilities or major domains | Hero → capability groups → workspace cards → supporting context | Landing Hero exception; actions navigate to capabilities | `app/templates/welcome/index.html`; `patterns/WELCOME_WORKSPACE_CATALOG.md` |
| **Overview** | Understand a domain's organization, current posture, coverage, and next destinations | Hero → posture/summary → grouped domain summaries → related destinations | Existing family Hero; low-to-moderate action density | `app/templates/kubernetes/inventory/overview/index.html`; `app/templates/integrations/overview.html`; `app/templates/reports/overview/index.html` |
| **Dashboard** | Perform a recurring operational scan and identify what needs attention now | Operational Dashboard Hero → KPIs/signals → prioritized evidence → recommended actions → drill-downs | `operational-dashboard` Hero profile; actions are prioritized and operational | `app/templates/kubernetes/dashboard/index.html`; `patterns/OPERATIONAL_DASHBOARD.md` |
| **Inventory / List** | Find, filter, compare, paginate, and inspect resource records | Hero → compact summaries when useful → filters → table/list → pagination → detail surface | Existing inventory-family Hero; row actions remain contextual | `app/templates/kubernetes/inventory/nodes/index.html`; `app/templates/kubernetes/inventory/pods/index.html`; `patterns/INVENTORY_RESOURCE_PAGE.md` |
| **Analytics** | Analyze evidence, trends, pressure, interpretation, and recommended review paths | Hero → scope/readiness → evidence/metrics → analysis/interpretation → recommendations | Existing Analytics Hero/component authority; actions drill into evidence or governed follow-up | `app/templates/kubernetes/analytics/overview/index.html`; `app/templates/kubernetes/analytics/capacity/index.html`; `app/templates/kubernetes/analytics/alerts/index.html` |
| **Operational Workspace** | Execute a governed operational mutation or live workflow | Hero/readiness → target/selection → operation workspace → validation/preview → execution feedback/evidence | One clear primary operation; blockers and destructive consequences stay visible | `app/templates/kubernetes/operations/configmaps/index.html`; Kubernetes Secret Operations workspace |
| **Configuration / Manage** | Configure and validate one managed integration, provider instance, or governed resource | Hero/identity → configuration → validation → runtime/readiness → scope/lifecycle | Configuration and validation actions are explicit; destructive actions are separated | `app/templates/integrations/observability/metrics_source/instance_detail.html`; `app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html`; `components/INTEGRATION_MANAGE_WORKSPACE.md` |
| **Detail / Inspector** | Inspect one selected resource, record, or relationship without recreating its parent list | Identity/context → evidence sections → relationships/history → contextual actions | Full-page detail may use the owning family Hero; modal/drawer inspectors do not add a nested Hero | `app/templates/components/resource_detail_modal.html`; `app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html` |
| **Workflow / Wizard** | Complete a bounded multi-step task with prerequisites, validation, review, and submission | Hero → prerequisite/readiness → ordered steps/form → preview/review → submit/result | Required fields, errors, blockers, and consequences are never hidden by tabs | `app/templates/reports/generate/index.html` |
| **Administration** | Manage KAORI users, roles, permissions, identity, account, or system settings | Hero → administrative summary/registry → forms/tables → security/permission feedback | Privileged and destructive actions are conservative and explicit | `app/templates/access/users/index.html`; `app/templates/access/roles/index.html`; `app/templates/access/identity_providers/index.html`; `app/templates/settings/general/index.html` |

## Overview vs Dashboard

These archetypes are intentionally different.

**Overview** answers:

- What exists in this domain?
- How is it organized?
- What is its current high-level posture or coverage?
- Where should the operator go next?

**Dashboard** answers:

- What needs attention now?
- What changed or is at risk?
- Which operational signals matter most?
- What should the operator review or act on next?

An Overview may summarize posture, but it must not become a dense operational cockpit. A Dashboard may link to Inventory and Analytics, but it must not replace their detailed resource or analytical evidence.

## Archetype Composition Boundaries

### Landing

- use capability/domain discovery rather than operational density;
- cards are destinations, not miniature dashboards;
- Landing remains the explicit Hero profile exception;
- mobile stacks capability groups using shared responsive behavior.

### Overview

- keep domain orientation and posture above detailed evidence;
- group summaries by stable capability or domain semantics;
- prefer links/drill-downs over duplicating full child workspaces;
- use committed KAORI state for normal operational rendering where the owning domain requires it.

### Dashboard

- optimize for repeated scanning;
- keep prioritized signals and actions visible without forcing tab-by-tab discovery;
- use the locked Operational Dashboard pattern and Hero profile;
- do not turn the Dashboard into a configuration or inventory-management surface.

### Inventory / List

- use canonical filters, table/list shell, labels, loading, empty/error state, and pagination;
- default server-paginated table size remains 5 unless the owning standard explicitly says otherwise;
- detailed evidence moves to the registered detail modal/drawer/full-detail pattern;
- bulk or destructive operations must follow the owning operational-workspace contract.

### Analytics

- distinguish evidence from interpretation and recommended action;
- preserve scope/readiness and freshness semantics;
- use the shared Analytics surface hierarchy and registered Content Tabs when tabs are appropriate;
- provider collection may be live, but normal page rendering follows the owning committed-state contract.

### Operational Workspace

- keep the operation target, readiness, validation, consequences, and feedback in the primary flow;
- tabs must not hide blockers, required fields, errors, or destructive consequences;
- use existing HTMX loading/toast/error/activity evidence ownership;
- mutation authority stays with the external engine/provider when the domain contract requires it.

### Configuration / Manage

- use existing configuration/manage components instead of provider-specific page shells;
- keep configuration, validation, runtime, scope, and lifecycle semantics distinct;
- use Framed Workspace Tabs only when the parent workspace shell is part of the information architecture;
- never turn a provider configuration page into the provider's replacement operational UI.

### Detail / Inspector

- preserve parent context and return path;
- do not duplicate the parent collection as a nested table merely to fill the surface;
- two or three local views may use Compact Segmented Tabs;
- modal/drawer viewport and focus behavior remain owned by the existing shared component.

### Workflow / Wizard

- express the bounded sequence explicitly;
- validation and review precede irreversible submission;
- a stepper or ordered flow is not permission to create a new tab style;
- incomplete or blocked steps remain understandable without relying on color alone.

### Administration

- use standard tables/forms and explicit privilege context;
- security-sensitive actions require the owning authorization/feedback contract;
- administrative density does not justify smaller page-local typography;
- settings sections may use registered navigation only when the relationship matches the tab decision matrix.

## Active Surface Classification

The following family-level map keeps current production surfaces deterministic without attempting to duplicate every route in design documentation.

| Surface family | Primary archetype |
| --- | --- |
| Welcome | Landing |
| Kubernetes operational dashboard | Dashboard |
| Kubernetes Inventory Overview | Overview |
| Kubernetes Inventory resource pages | Inventory / List |
| Kubernetes Topology | Detail / Inspector with the registered visualization-workspace specialization |
| Kubernetes Analytics Overview and leaf analysis pages | Analytics |
| Kubernetes ConfigMap / Secret Operations | Operational Workspace |
| Object Storage Inventory | Inventory / List |
| Object Storage Analytics | Analytics |
| Integrations Overview and capability-domain pages | Overview |
| Integration provider instance detail/manage | Configuration / Manage |
| Intelligence analytical/evidence workspaces | Analytics unless the route's primary intent is an operation |
| Rule/record registries and Activity Audit | Inventory / List |
| Automation Control and equivalent governed execution surfaces | Operational Workspace |
| Reports Overview | Overview |
| Reports Generate | Workflow / Wizard |
| Generated Reports / Report Templates / Schedules registries | Inventory / List, with Configuration / Manage used only for a concrete managed record |
| Access and Settings management | Administration |
| Full-page resource/record details | Detail / Inspector |
| Platform Operations mutation workspaces | Operational Workspace |

Where a family contains materially different route intents, classify the route rather than assigning one archetype to the entire module.

## Navigation and Tab Decision Matrix

Tabs are optional. A page should use no tabs when sections, routes, cards, or a detail surface express the information architecture more clearly.

| Decision | Approved family | Semantic key | Shared owner | Production reference |
| --- | --- | --- | --- | --- |
| Two or three mutually exclusive **local** views inside one component, visualization, drawer, or inspector | **Compact Segmented Tabs** | `compact-segmented` | `components/segmented_tabs.html` | Kubernetes Topology Graph/List and Details/Relationships |
| Several closely related **content views subordinate to an established workspace** | **Content Tabs** | `content-tabs` | `components/content_tabs.html` | Kubernetes/Object Storage Analytics; Alert Intelligence |
| Peer operational domains where an **explicit framed parent workspace** is part of the information architecture | **Framed Workspace Tabs** | `framed-workspace-v2` | `components/framed_workspace_tabs.html` | Kubernetes Integration detail and Integration Overview |
| Peer sections that **define the workspace itself** and should attach through a simple divider without a parent card | **Integrated Workspace Tabs** | `integrated-workspace` | `components/workspace_tabs.html` | Kubernetes Operations Dashboard |
| No tab relationship is required | **No Tabs** | n/a | sections/routes/cards/detail navigation | Welcome, ordinary Inventory resource pages, Reports Generate |

### Deterministic Selection

Use this order:

```text
2–3 local mutually exclusive views?
  → Compact Segmented Tabs
else closely related subordinate content views in an established workspace?
  → Content Tabs
else peer domains inside an explicit framed parent workspace?
  → Framed Workspace Tabs
else peer sections that define one workspace?
  → Integrated Workspace Tabs
else
  → No Tabs
```

**Content Tabs vs Integrated Workspace Tabs:** Content Tabs are subordinate navigation inside a workspace that already has its identity and primary composition. Integrated Workspace Tabs define major peer sections of the workspace itself.

**Framed vs Integrated Workspace Tabs:** use Framed Workspace Tabs only when the parent frame is semantically meaningful. Visual preference for a card is not sufficient.

A new fifth tab style requires a materially different information architecture, registration in `components/TAB_STYLES.md`, a shared semantic owner, a production reference, and governed review. Color, radius, spacing, icon placement, or provider branding never justify a new style.

## State and Responsive Placement

This registry determines composition, not a parallel state system.

Pages continue to consume the existing shared loading, empty, error, blocked, degraded, stale/partial, permission, modal/drawer, accessibility, and responsive contracts. Exact cross-archetype state/interaction consolidation is owned by #608.

At minimum:

- Hero/profile identity remains stable across supported operational states;
- blockers and errors stay adjacent to the operation or evidence they govern;
- responsive behavior comes from shared components and existing patterns, not device-specific page CSS;
- tables, cards, actions, modals, drawers, and tab overflow follow their registered component contracts;
- mobile is an adaptive composition, not a compressed desktop.

## Extension and Exception Rule

A page may be an explicit archetype exception only when existing semantics cannot represent its operator intent. The exception must:

1. identify the missing semantic need;
2. show why the nearest existing archetype cannot represent it;
3. avoid page-local visual invention as a temporary workaround;
4. be tracked as bounded follow-up work before becoming a reusable pattern.

Do not register a new archetype solely because one domain uses different nouns, metrics, providers, or data sources.

## Follow-on Ownership

This registry intentionally leaves adjacent Design System v2 work to its existing bounded owners:

- #607 — foundation and content-density matrices;
- #608 — responsive, accessibility, state, and interaction matrices;
- #609 — exact production-reference and enforcement coverage map plus extension policy.

No additional design-system gap is required by this classification review.

## Verification Ownership

#606 extends existing design contract coverage only. It does not add a verifier.

Expected validation:

- `tests/contracts/design/test_kaori_styling_guide_contract.py`;
- existing UI reuse/style verifiers selected by Developer Check;
- documentation/style checks selected by Developer Check;
- fresh staging Full Admission after merge.

There is no runtime/UI visual baseline change in this workstream. Final Design System v2 human visual UAT remains owned by parent #572.
