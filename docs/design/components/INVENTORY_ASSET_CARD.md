# Inventory Asset Card

## Purpose

The Inventory Asset Card is a destination card for one Kubernetes inventory asset type. It combines the current object count with a direct link to the owning asset inventory.

Shared implementation:

```text
app/templates/components/inventory_asset_card.html
```

## Canonical Content

- asset icon;
- current committed object count;
- asset title;
- one-sentence functional description;
- `Open Inventory` destination action.

## Visual Contract

- `rounded-xl` standard card;
- 40 px Violet-soft icon surface;
- count uses `text-2xl font-semibold`;
- title uses `text-base font-semibold`;
- description uses `text-xs leading-5`;
- restrained border and shadow change on hover;
- no translation, heavy shadow, pill label, or page-local geometry.

## Usage Boundary

Use this component for navigable inventory asset catalogs. Do not use it for status, health, readiness, or a non-clickable KPI.
