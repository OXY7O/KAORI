# Operational Workflow Catalog Row

## Purpose

`components/operational_workflow_catalog.html` owns the catalog shell and `components/operational_workflow_card.html` presents one destination row inside it. Despite the compatibility filename, the canonical presentation is a **flat catalog row**, not a stack of floating cards.

## Ownership

The component owns:

- natural-height row geometry inside one catalog surface;
- workflow identity and concise functional purpose;
- permission state (`Available` or `Restricted`);
- operation classification (`Standard`, `Controlled`, `Protected`, or `Destructive`);
- compact validation and authority evidence;
- one compact destination action and an optional secondary administration action;
- readable light- and dark-mode hover treatment.

Permission state and operation classification are separate concepts. Access to a protected operation must not change the permission label to `Protected`.

## Canonical geometry

The landing page owns one rounded catalog surface. Workflow rows are separated by subtle horizontal dividers:

```text
Operational Workflow Catalog
├── Icon | Workflow | Validation / Authority | Action
├── Icon | Workflow | Validation / Authority | Action
└── Icon | Workflow | Validation / Authority | Action
```

Rows use `surface-card` by default and `surface-hover` on hover or focus-within. Do not place bordered metric boxes inside each workflow row.

## Rules

- Do not use fixed minimum heights.
- Do not render each workflow as a separate floating card.
- Keep descriptions to one concise sentence.
- Keep validation and authority evidence as compact text, not nested cards.
- Use neutral surfaces. Critical color belongs to consequences and final destructive confirmation, not the catalog row.
- Disabled workflows show `Permission Required` and do not expose an active link.
- Desktop rows reserve one stable action column. Destination and optional administration controls fill that column with secondary or quiet-button treatment; do not turn row actions into solid-Violet blocks.
- Secondary actions are only for a directly related authority workspace, such as reveal-policy administration, and stack below the destination action so the evidence columns do not shift.
- Hover must preserve readable contrast in light and dark appearance.
- Landing pages must not repeat the entire validation procedure below every workflow.

## Canonical usage

ConfigMap Management:

```text
Create ConfigMap
Update ConfigMap
Delete ConfigMap
```

Secret Management:

```text
Create Secret
Replace Secret Data
Delete Secret
Protected Secret Reveal
TLS Rotation
```
