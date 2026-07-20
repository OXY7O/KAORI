# Context Guidance Card — Integrations Audit — July 2026

## Objective

Extract the visual and content pattern used by **After Registration** on Register Alertmanager Instance, define it as a reusable KAORI component, and apply it to relevant right-side guidance across Kubernetes, Prometheus, and Alertmanager integration workspaces.

## Reference pattern

The reference implementation contained:

- native expandable behavior;
- compact icon, title, and description header;
- Details / Collapse control;
- compact 12 px guidance copy;
- inline two-digit markers;
- Title Case item labels followed by sentence-case explanations.

This pattern is now named **Context Guidance Card**.

## Audit scope

Reviewed contextual sidebars and guidance blocks in:

- Kubernetes connection detail;
- Prometheus register/edit connection;
- Prometheus connection detail;
- Prometheus cluster configuration;
- Alertmanager register/edit instance;
- Alertmanager instance configuration;
- Alertmanager capability validation.

Overview, landing, list, registry, dynamic readiness, live diagnostics, destructive actions, and Related Page Cards were reviewed but excluded because they have different semantic responsibilities.

## Findings

Before migration, equivalent guidance used several local variants:

- static white cards with numbered badges;
- blue information blocks containing full process descriptions;
- non-expandable lifecycle lists;
- locally copied expandable details markup;
- inconsistent marker shapes, title sizes, borders, and padding.

The content was semantically similar but visually fragmented.

## Implementation

### Shared component

Added:

```text
app/templates/components/context_guidance_card.html
```

The component supports:

- ordered or unordered items;
- generated two-digit markers;
- configurable icon;
- default-open behavior for essential guidance;
- native keyboard-accessible expansion.

### Alertmanager register/edit instance

Migrated:

- Connection Type Guide;
- Connection Identity & Contract;
- After Registration;
- Connection Lifecycle.

`After Registration` remains the visual reference and now consumes the shared component rather than local markup.

### Alertmanager instance configuration

Migrated:

- Configuration Flow;
- Connection Type.

The previous unnecessary Violet emphasis on Connection Type was removed. It is explanatory guidance, not a warning or status.

### Alertmanager validation

Migrated:

- When External Criteria Already Pass.

The remediation sequence now uses concise Title Case step labels and generated two-digit markers.

### Prometheus register/edit connection

Migrated:

- Prometheus Integration Flow.

The component is open by default because this page has no separate primary Info Flow and the registration sequence is essential. The distinct Connection Versus Capability semantic note remains outside the component because it communicates an operational boundary.

### Prometheus connection detail

Migrated:

- Operational Flow.

The current Change Impact semantic message remains a status-impact notice and was not converted.

### Prometheus cluster configuration

Migrated:

- Configuration Flow.

The Cluster Binding context remains a separate factual card.

### Kubernetes connection detail

Migrated:

- Operational Flow.

The Authority Boundary semantic information box remains separate because it communicates the authoritative-source boundary, not a general guidance list.

## Exclusions

The following remain separate by design:

- Related Page Card: one destination navigation action;
- Info Flow: primary page workflow with larger timeline hierarchy;
- current readiness or diagnostic evidence;
- warning and critical notices;
- destructive lifecycle controls;
- factual identity, binding, and status cards.

## Documentation updates

Added:

```text
docs/design/components/CONTEXT_GUIDANCE_CARD.md
```

Updated:

```text
docs/design/README.md
docs/design/DESIGN_SYSTEM.md
docs/design/KAORI_DESIGN_SYSTEM.md
docs/design/components/INFO_FLOW.md
```

## Guardrails

Added:

```text
tests/ui/test_context_guidance_card_contract.py
```

The guardrail prevents:

- reintroducing local After Registration markup;
- losing native details/summary behavior;
- removing two-digit generated markers;
- using the component without documentation;
- replacing semantic state boxes or Related Page Cards with guidance cards.

## Result

Right-side integration guidance now uses one documented component with consistent hierarchy, geometry, casing, expansion behavior, and compact item formatting.
