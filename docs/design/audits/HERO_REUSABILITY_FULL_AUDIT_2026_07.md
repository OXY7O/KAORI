# KAORI Hero Reusability Full Audit — July 2026

> **Status: Historical audit snapshot.** Counts and page lists in this document are retained as migration evidence, not as the active contract. Use `docs/design/components/HERO.md` and `scripts/verify_hero_component_standard.py`.


## Baseline

The visual baseline is the shared pattern used by **Infrastructure Integrations** and **Kubernetes Integrations**:

- Violet outer shell;
- stable 7/5 desktop grid;
- identity eyebrow and leading icon;
- one page title;
- one concise supporting description;
- two or three metadata labels;
- compact right-side context panel;
- no more than two visible Hero actions.

## Audit Scope

The audit covers **74 authenticated KAORI Hero templates** across Welcome, Access, Settings, Integrations, Kubernetes Operations, Inventory, Analytics, Governance, Intelligence, Reports, Notifications, Prometheus, Alertmanager, and access-denied handling.

## Shared Ownership

`app/templates/components/page_hero.html` is the single source of truth for:

- shell height, radius, padding, border, and Violet surface;
- responsive 7/5 layout;
- content and aside alignment;
- title and description typography;
- metadata spacing;
- right-side context panel geometry;
- context icon, metric card, label, value, and description styling;
- one-column and two-column context action layouts;
- primary and secondary Hero actions.

Domain components may own content and semantic status logic, but they must compose the shared primitives. They must not copy Hero utility classes locally.

## Normalized Areas

The patch removes local Hero geometry from:

- Infrastructure, Kubernetes, Prometheus, and Alertmanager integrations;
- integration jobs, bindings, detail, and registration workflows;
- Kubernetes Inventory and Analytics Hero partials;
- Kubernetes ConfigMap and Secret operation workflows;
- dashboard, cluster, governance, and intelligence workspaces;
- reports overview, schedules, storage, generation, registry, and detail pages;
- Access, Settings, User, identity provider, and LDAP workflows;
- Welcome and Access Denied pages.

The generated report detail Hero was also reduced to two visible actions. Artifact regeneration, archive, and restore controls now live in a separate lifecycle action block below the Hero.

## Automated Guardrail

`scripts/verify_hero_component_standard.py` now verifies:

- the complete Hero estate is still discovered;
- required shared macros remain available;
- every authenticated Hero uses shared shell, layout, content, intro, title, description, metadata, and context contracts;
- legacy local Hero geometry does not return;
- unmanaged authenticated Violet Heroes are rejected;
- Infrastructure Integrations and Kubernetes Integrations remain reference implementations.
