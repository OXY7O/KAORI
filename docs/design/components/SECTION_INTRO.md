# KAORI Section Intro Standard

## Purpose

`components/section_intro.html` owns the plain heading hierarchy used immediately above a major operational workspace, registry, table, visualization, or grouped card section.

It is the shared presentation extracted from the accepted Tenant Overview hierarchy such as **Multi-Cluster Posture** and **Operational Attention**.

## Contract

A Section Intro is contextual hierarchy only. It is:

- not a Hero;
- not a card;
- not a replacement for the owning workspace/card title;
- not a second action bar;
- not a place for metric values.

The default composition is:

```text
Section Title
Concise supporting description
[optional quiet supporting note aligned right]
↓
Owning card / table / visualization / peer workspace
```

Use `section_intro.render(title, description, id, supporting)`.

## Wording

The outer section title describes the operator's perspective or information group. The child surface title names the concrete object/workspace.

Good:

```text
Operational Posture
└── Node Resource Posture

Inventory Records
└── Node Inventory

Certificate Inventory
└── TLS Certificate Registry

Multi-Cluster Inventory
└── Cluster Inventory Summary
```

Avoid repeating the same semantic title at both levels.

## Visual contract

- section title: `text-lg font-semibold text-content-primary`;
- description: `text-sm leading-6 text-content-secondary`;
- optional supporting note: `text-xs leading-5 text-content-muted`;
- no local background, border, shadow, or palette;
- no page-local copies of these classes on surfaces adopting this standard.

## Accessibility

When the intro labels a semantic `section`, provide the same `id` to `section_intro.render(...)` and reference it with `aria-labelledby` on the owning outer section.

## Reference surfaces

- Kubernetes Tenant Overview;
- Kubernetes Inventory Overview and resource pages;
- Kubernetes Inventory Topology;
- TLS Certificate Governance.

Domain content may vary, but the hierarchy and typography remain shared.
