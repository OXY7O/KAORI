# Operational Workflow Card

## Purpose

`components/operational_workflow_card.html` presents one destination in an operational workflow catalog. It is used when a landing page offers several distinct mutation or protected-access workflows.

## Ownership

The component owns:

- natural-height card geometry;
- workflow identity and concise functional purpose;
- permission state (`Available` or `Restricted`);
- operation classification (`Standard`, `Controlled`, `Protected`, or `Destructive`);
- validation and authority boundaries;
- one primary destination action and an optional secondary administration link.

Permission state and operation classification are separate concepts. Access to a protected operation must not change the permission label to `Protected`.

## Rules

- Do not use fixed minimum heights to align cards.
- Keep descriptions to one concise sentence.
- Use neutral card surfaces. Critical color belongs to consequences and final destructive confirmation, not the entire catalog card.
- Disabled workflows show `Permission Required` and do not expose an active link.
- Secondary actions are only for a directly related authority workspace, such as reveal-policy administration.
- Landing pages must not repeat the entire validation procedure below every card.

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
