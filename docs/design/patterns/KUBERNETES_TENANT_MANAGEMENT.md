# Kubernetes Tenant Management UI Foundation

**Status: PRE-IMPLEMENTATION CONTRACT — not release-visible.**

## Purpose

Define the KAORI user-experience authority for **Kubernetes Governance → Tenant Management** before production routes, permission keys, provider adapters, or mutation workflows are exposed.

This contract belongs to #125 and is intentionally preparatory. It converts the approved Tenant Management product model into a stable UI information architecture while preserving the current admitted application shell. It does not claim that #112–#123 are implemented or that Tenant Management is ready for release.

## Product Boundary

Tenant Management is one governed product workspace. It must have **one global sidebar destination** under **Kubernetes Governance**.

Do not create eleven global sidebar links, Native/Capsule duplicate navigation trees, provider-specific top-level parents, or a separate application-shell section.

The current release-visible Kubernetes Governance menu remains unchanged until the activation criteria in this contract are satisfied.

## Internal Information Architecture

The Tenant Management workspace owns these internal destinations in this order:

- Overview
- Tenants
- Namespaces
- Members & Access
- CI/CD
- Credentials
- Resource Profiles
- Managed Resources
- Policies
- Activity
- Providers

These are internal workspace destinations, not global sidebar parents.

### Overview

Overview summarizes committed Tenant Management posture without duplicating the domain pages:

- tenant, environment, and namespace posture;
- resource-profile and managed-resource posture;
- access and credential attention;
- policy and provider health;
- prioritized operator actions;
- evidence freshness and committed/runtime distinction where relevant.

### Domain Pages

Each domain page owns one primary responsibility:

| Destination | Primary responsibility |
| --- | --- |
| Tenants | Tenant identity, lifecycle, environments, ownership, and provider binding evidence. |
| Namespaces | Managed tenant namespaces, environment, cluster, Resource Profile, reconciliation, and drift. |
| Members & Access | Users, groups, access grants, role profiles, scope, revoke state, and effective-access evidence. |
| CI/CD | Governed deployment identities and purpose-bound delivery evidence. |
| Credentials | Human and machine credential lifecycle metadata without routine secret exposure. |
| Resource Profiles | Small, Standard, Large, and Custom quota/profile contracts. |
| Managed Resources | KAORI-owned tenancy resources, committed/effective state, reconciliation, and drift. |
| Policies | Domain, exposure, registry, production, and other tenant-governance policy posture. |
| Activity | Tenant-scoped operational and correlated Kubernetes activity evidence. |
| Providers | Active provider, capability readiness, degradation, recovery, version, and authority evidence. |

## Provider-Neutral Presentation

**Native Kubernetes** is the baseline provider. **Capsule** is a capability unlock.

The information architecture, labels, table patterns, page hierarchy, and operator workflow remain stable regardless of provider. Provider changes affect capability availability and evidence, not product structure.

Do not fork the UI into "Native Tenant Management" and "Capsule Tenant Management".

Provider-specific technical evidence belongs in the Providers page, detail surfaces, or bounded capability context. User-facing domain pages continue to speak the canonical Tenant Management language.

## Capability State Contract

Every capability-dependent control must render one explicit state rather than optimistically assuming executability.

### unavailable

Use when the active provider/cluster cannot enforce or execute the capability.

- keep the relevant state visible when operationally useful;
- disable or omit mutation controls according to the shared KAORI action contract;
- explain the missing capability and required next step;
- do not imply that a database-only change will be enforced.

### degraded

Use when the provider or required enforcement path is unhealthy or ambiguous.

- preserve committed/effective evidence;
- show the degraded authority clearly;
- security-sensitive mutations fail closed;
- existing readable evidence remains available where safe.

### read-only / recovery

Use during governed recovery, authority transfer, or states where evidence may be inspected but normal mutations are intentionally blocked.

- clearly identify recovery ownership;
- expose the recovery/review path;
- do not silently fall back from Capsule to Native Kubernetes;
- do not present blocked controls as ordinary validation errors.

### actionable

Use only when authorization, provider capability, committed prerequisites, and runtime readiness permit the operation.

An actionable UI state never replaces server-side authorization or provider-side enforcement.

## Authorization Boundary

No `tenant_management.*` permission currently exists in the admitted KAORI permission registry.

For this pre-implementation contract, **permission keys remain reserved until backend authorization ownership is admitted** through the canonical Tenant Management domain/access work.

Minimum authority dependencies:

- #112 establishes the canonical Tenant Management domain and provider-neutral ownership boundary.
- #114 establishes membership, access profiles, access grants, and the effective authorization model.
- #125 consumes the admitted authorization contract for presentation and route visibility.

Rules:

1. Do not invent production permission keys in templates or navigation before the code-owned permission registry is updated through the normal migration/contract flow.
2. Sidebar visibility is secondary to server-side route/service authorization.
3. Sensitive credential actions require distinct authorization from routine metadata visibility.
4. Provider availability never grants user authorization.
5. A user-visible disabled state must not be the only enforcement boundary.

## Application-Shell Integration

When activation criteria are met, Tenant Management becomes one child of the existing Kubernetes Governance parent.

The integration must preserve `SIDEBAR_NAVIGATION.md`:

- parent geometry and typography remain unchanged;
- Tenant Management is a submenu item, not a new top-level section;
- active-state ownership belongs to `governance_menu.html`;
- global permission gating remains owned by the application shell;
- breadcrumbs must root at **Kubernetes Governance** and then **Tenant Management**;
- no provider-specific color is introduced into navigation.

Before activation, no Tenant Management menu item is release-visible.

## Page Composition Standard

Tenant Management inherits the current KAORI Violet design system and shared component contracts.

### Hero

The Hero communicates:

- Kubernetes Governance / Tenant Management context;
- current workspace title and bounded description;
- tenant/environment/cluster/provider context when relevant;
- committed/readiness metadata;
- one prioritized action group only when actionable.

Blocked or degraded readiness is additive. It must not remove operational metadata that remains useful.

### Internal navigation

The eleven destinations use one Tenant Management workspace navigation model. They must not become nested global sidebar branches.

Desktop and laptop may render the workspace navigation as a persistent in-content module navigation surface. Tablet/mobile must adapt it without document-level horizontal overflow and without hiding destinations.

### Tables

Use the canonical KAORI table contract:

- left-aligned content;
- rightmost action aligned right;
- default page size 5 with 5/10/25/50 options where pagination applies;
- HTMX loading behavior where the owning page is HTMX-backed;
- explicit loading, empty, error, degraded, and permission-denied states;
- local horizontal scrolling only when dense technical columns cannot be safely reduced.

Primary tenant identity, environment/scope, state, and primary operator action must remain understandable without zoom.

### Detail surfaces

Use the canonical modal/drawer/detail contracts. Do not create provider-specific detail geometries.

Dense secondary evidence such as provider capability/version, effective RBAC, reconciliation IDs, and technical Kubernetes metadata belongs in a bounded detail surface rather than widening the primary table.

## Sensitive Credential Presentation

Routine list, navigation, search, Activity, and detail surfaces must never expose credential secret material.

Allowed routine presentation includes:

- credential identity/type;
- owner/purpose;
- tenant/environment/namespace scope;
- lifecycle state;
- issue/expiry/renewal/revoke timestamps;
- provider/effective enforcement evidence;
- last governed delivery/reference metadata where safe.

Any future reveal/download flow must reuse KAORI protected-value and sensitive-operation patterns, require explicit authorization, and create Activity evidence. Secret values must never be written to Notification Deck or ordinary Activity payloads.

## Mutations and Evidence

Successful governed mutations must follow existing KAORI operational feedback patterns:

- immediate form/action feedback;
- toast where appropriate;
- Notification Deck evidence for meaningful asynchronous/operator events;
- Activity evidence with actor, scope, result, and correlation identity;
- committed state separated from live/effective reconciliation state.

A failed provider operation must not leave the UI presenting the intended state as successfully enforced.

## Responsive Contract

Tenant Management inherits the #224 adaptive shell and canonical viewport policy.

Mobile is an adaptive operational surface, not a squeezed desktop workspace.

Requirements:

- one global Tenant Management destination remains reachable from the off-canvas Kubernetes Governance navigation;
- internal workspace navigation recomposes for narrow screens;
- no page-level horizontal overflow;
- forms and filter rows stack or move into mobile-safe filter/action surfaces;
- dense tables use local scrolling, record summaries, or detail drawers;
- complex drawers/modals become near-full-screen/full-screen where required;
- touch targets, accessible names, focus order, and Escape/backdrop behavior follow existing shell standards;
- light/dark behavior uses existing tokens without provider-specific overrides.

Samsung-specific CSS is prohibited.

## Accessibility Contract

All Tenant Management surfaces must preserve:

- semantic headings and landmark order;
- keyboard-reachable navigation and actions;
- visible focus;
- explicit accessible names for icon-only controls;
- correct disclosure/dialog semantics;
- validation association for forms;
- status meaning that is not color-only;
- focus restoration after dialogs/drawers where the shared component contract requires it.

Provider capability state must be understandable from text and semantics, not color alone.

## Activation Criteria

This document may be merged as a pre-implementation design authority, but production Tenant Management UI must remain hidden until the applicable dependencies are admitted.

Before adding the release-visible route/menu:

1. #112 domain/provider abstraction is admitted.
2. #114 authorization/access ownership is admitted.
3. The applicable #113–#123 capabilities required by the first production slice are admitted.
4. A real server-side Tenant Management endpoint/service boundary exists.
5. Canonical permission keys are code-owned, migrated, and enforced.
6. Kubernetes Governance navigation and breadcrumb ownership are updated deliberately.
7. Release-surface registration and relevant architecture contracts are updated.
8. Existing sidebar, UI, accessibility, security, and authorization gates remain green.
9. #124 Capsule-only capabilities are exposed only when their discovered provider capability is compatible; #124 does not block the Native Kubernetes baseline.

## Verification

Implementation under #125 must use existing KAORI quality gates and tests. Do not add a custom verification script solely for Tenant Management UI.

Expected verification includes:

- presentation/navigation/permission contracts;
- Jinja and DjLint;
- Ruff and Pyright for supporting Python;
- existing sidebar/navigation verifiers when release-visible navigation changes;
- browser interaction coverage through the existing Playwright authority;
- accessibility and responsive coverage at the canonical viewports;
- authorization negative tests;
- Native Kubernetes end-to-end UAT for baseline completion;
- Capsule UAT only when an approved compatible live capability exists.

## Change Control

This contract is preparatory and may evolve while #112–#124 establish the backend/provider capabilities, but changes must preserve the core product decisions already approved in #61/#125:

- one Tenant Management product;
- one global sidebar destination;
- provider-neutral UX;
- Native Kubernetes baseline;
- Capsule capability unlock;
- explicit capability/degradation evidence;
- fail-closed sensitive mutations;
- no routine credential secret exposure.
