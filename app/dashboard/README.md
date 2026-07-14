# KAORI Welcome and Dashboard Domain

This document defines the product and access contract for the KAORI entry workspace. Use it as the baseline when extending the Welcome page, navigation, RBAC, or infrastructure-domain coverage.

## Platform Positioning

KAORI is a unified infrastructure operations platform for:

- observability;
- analytics;
- governance; and
- intelligent recommendations.

The primary infrastructure asset domains are:

1. Kubernetes;
2. Server; and
3. HCI.

A module may be implemented for one domain before the others, but UI wording must preserve the unified KAORI identity. Avoid positioning KAORI as only a Kubernetes product or describing Server and HCI as unrelated products. Domain-specific implementation status should be stated locally without changing the platform identity.

## Welcome Page Contract

`/welcome` is the first page shown after a successful login.

Technical rules:

- Every authenticated user can open Welcome, regardless of assigned role.
- The route must remain protected by `login_required` and must not use a feature permission as an access gate.
- Welcome must not query live infrastructure integrations merely to render the landing page.
- The page summarizes KAORI and exposes direct shortcuts to major workspaces.
- Shortcut visibility is RBAC-aware. A shortcut is rendered only when the user has permission to open its resolved destination.
- Restricted workspaces are omitted rather than displayed as disabled or "No access" cards.
- Account and personal settings remain available as the baseline destination for all authenticated users.
- A multi-purpose shortcut may resolve to the first accessible destination in priority order. For example, Reports can open Overview, Generate, Templates, Schedules, or Storage depending on the user's permissions.

Shortcut definitions and permission-to-endpoint resolution are maintained in:

- `app/dashboard/routes.py` — `_WELCOME_SHORTCUT_DEFINITIONS` and `_build_welcome_shortcuts()`.

Welcome presentation is maintained in:

- `app/templates/dashboard/welcome.html`.

## Welcome Design Standard

The Welcome page follows the shared KAORI layout language:

- blue-to-cyan gradient hero;
- rounded `3xl` surfaces;
- restrained shadows instead of prominent white outlines;
- a visually elevated blue posture/scope card on the right side of the hero;
- concise one-purpose labels;
- role and workspace-count context in the hero;
- responsive shortcut cards with consistent icon, asset-domain label, description, and action placement;
- complete light and dark mode support.

Do not reintroduce a dark slate hero, roadmap-centric wording, disabled shortcut cards, or Kubernetes-only platform positioning.

## Dashboard Boundary

Welcome and the Kubernetes Operations Dashboard serve different purposes:

- **Welcome** is a lightweight, universal, role-aware entry workspace.
- **Kubernetes Operations Dashboard** is a permission-controlled operational command center and may load inventory, Prometheus, Alertmanager, reporting, and recommendation context.

Keep the two routes separate. Welcome must remain useful even when no Kubernetes cluster has been registered or when a user cannot access the operational dashboard.
