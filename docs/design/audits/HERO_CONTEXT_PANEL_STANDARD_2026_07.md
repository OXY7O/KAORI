# Hero Context Panel Standard Audit — July 2026

> **Status: Historical audit snapshot.** This file records the July 2026 migration and is not an implementation contract. Use `docs/design/components/HERO.md` and `scripts/verify_hero_component_standard.py` for the active standard.


## Scope

This audit compared the Node Inventory hero against the Alertmanager Integrations and Alertmanager instance-detail heroes. The Node Inventory right-side posture panel was selected as the baseline because it provides the clearest hierarchy between posture identity, semantic status, compact metrics, and one operational action.

## Standard established

The shared `page_hero` component now owns the right-side context-panel geometry and metric-card treatment. Page templates no longer need to reproduce these utility strings locally.

Required panel hierarchy:

`Posture Eyebrow → Panel Title → Semantic Status → Two Metrics → One Action`

The context panel remains a compact operational summary and is not used as a mini-dashboard.

## Implementation

Updated:

- `app/templates/components/page_hero.html`
- `app/templates/inventory/kubernetes/nodes/partials/_hero.html`
- `app/templates/integrations/alertmanager.html`
- `app/templates/alertmanager/instance_detail.html`

The Alertmanager Integrations panel now follows the Node Inventory baseline with a 208 px minimum height, two descriptive metric cards, a semantic status badge, and one full-width action.

## Metadata casing

Human-readable hero metadata now uses Title Case. Technical identifiers preserve canonical casing and are not passed through a mechanical title filter.

Examples normalized:

- `4 Nodes Tracked`
- `64 CPU Cores`
- `3 Registered Instances`
- `2 Scope Bindings`
- `6 Capabilities`

## Validation

- Jinja parsing passed for all modified templates.
- Python compilation passed.
- `scripts/verify_hero_component_standard.py` is the current automated guardrail.
