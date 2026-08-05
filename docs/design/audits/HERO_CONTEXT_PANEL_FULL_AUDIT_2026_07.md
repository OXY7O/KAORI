# Hero Context Panel Full Audit — July 2026

> **Status: Historical audit snapshot.** Counts in this document describe the July 2026 estate only. The current estate is discovered dynamically by `scripts/verify_hero_component_standard.py`. Use `docs/design/components/HERO.md` for implementation decisions.


## Scope

The audit reviewed all 72 templates that import the shared `page_hero` component and all 31 Hero templates that render a right-side context panel through `page_hero.aside_classes()`.

## Contract Applied

Every right-side Hero context panel now uses:

```jinja
<div class="{{ page_hero.context_panel_classes() }}">
```

This establishes the Node Inventory Hero as the common structural baseline:

1. posture eyebrow;
2. concise panel title;
3. optional semantic status;
4. no more than two compact metrics when metrics are present;
5. no more than one primary full-width action;
6. minimum panel height of 13 rem;
7. full-height alignment with the Hero content column.

Content variants remain valid when a page needs policy guidance, release information, or a short workflow explanation instead of metrics. Those variants must still use the same panel geometry, typography roles, surface, border, and density.

## Audit Result

| Item | Result |
|---|---:|
| Templates importing `page_hero` | 72 |
| Hero right-side panels audited | 31 |
| Panels using the shared context-panel wrapper | 31 |
| Legacy local 12 rem panel wrappers remaining | 0 |
| Node Inventory baseline retained | Yes |
| Alertmanager integration implementation retained | Yes |

## Metadata Casing

Human-readable Hero metadata uses Title Case, including count labels and operational summaries:

- `4 Nodes Tracked`
- `3 Registered Connections`
- `2 Scope Bindings`
- `6 Active Alerts`
- `12 Activities Recorded`

Technical identifiers preserve canonical casing:

- `kube-system`
- `v1beta1`
- `prometheus-v3`
- `OAuth`
- `OIDC`
- `ConfigMap`

Do not apply the Jinja `title` filter to an entire metadata value when it can contain a technical identifier. Capitalize only the human-readable label fragment in the template or presentation layer.

## Pages Normalized

The migration covers Hero context panels across:

- Alertmanager;
- analytics;
- cluster management;
- governance;
- integrations;
- intelligence;
- inventory;
- notification activity;
- Prometheus;
- reports;
- settings;
- users and identity providers.

## Guardrails

The automated contract prevents:

- local copies of the legacy `min-h-[12rem]` Hero panel wrapper;
- Hero asides that do not use `page_hero.context_panel_classes()`;
- lower-case human-readable metadata suffixes that have already been standardized;
- removal of the Node Inventory and Alertmanager reference implementations.
