# Information Guide Card — Integrations Audit — July 2026

## Objective

Review right-side Integration guidance that was visually similar to **After Registration** but did not represent an ordered sequence. Extract a distinct non-sequential component, add related icons to every item, and remove misleading numbering from option and contract references.

## Audit scope

Reviewed shared and page-local guidance in:

- Register/Edit Alertmanager Instance;
- Alertmanager Instance Configuration;
- Kubernetes connection detail;
- Prometheus register/edit connection;
- Prometheus connection detail;
- Prometheus cluster configuration;
- Alertmanager validation guidance.

## Findings

Three Alertmanager guidance blocks required semantic correction:

| Block | Previous Representation | Finding | Resolution |
|---|---|---|---|
| Connection Type Guide | Unordered text in Context Guidance Card | Correctly non-sequential, but lacked item identity and visual scanning support | Move to Information Guide Card with related icons |
| Connection Identity & Contract | Numbered Context Guidance Card | Concepts were peers, not steps; numbering incorrectly implied execution order | Move to Information Guide Card with contract-specific icons |
| Connection Lifecycle | Unnumbered Context Guidance Card | Save, Full Validation, and Enabled describe lifecycle progression | Keep Context Guidance Card and enable ordered markers |

The same Connection Type reference on Alertmanager Instance Configuration also used an unordered generic list and was migrated.

## Standard introduced

Added:

```text
app/templates/components/information_guide_card.html
```

The shared component provides:

- native expandable behavior;
- compact KAORI Violet header;
- icon-led peer items;
- subtle dividers;
- no numbering or timeline connector;
- two-to-five-item contract;
- no embedded actions.

## Implemented icons

### Connection Type Guide

- Externally Managed → `building-2`;
- Standalone → `box`;
- Shared Service → `network`;
- Managed for a Specific Scope → `target`.

### Connection Identity & Contract

- Connection Identity → `fingerprint`;
- Connection Contract → `file-check-2`;
- Capability Contract → `badge-check`;
- Scope Bindings → `link-2`.

The icons identify concepts and do not communicate severity or sequence.

## Integration audit result

Ordered guidance retained the Context Guidance Card:

- After Registration;
- Connection Lifecycle;
- Configuration Flow;
- Operational Flow;
- Prometheus Integration Flow;
- When External Criteria Already Pass.

Non-sequential peer guidance uses the Information Guide Card:

- Connection Type Guide;
- Connection Identity & Contract.

No Kubernetes or Prometheus block required migration in this audit because their current Context Guidance Card usage represents actual ordered flow.

## Documentation updates

Added:

```text
docs/design/components/INFORMATION_GUIDE_CARD.md
docs/design/audits/INFORMATION_GUIDE_CARD_INTEGRATIONS_AUDIT_2026_07.md
```

Updated:

```text
docs/design/components/CONTEXT_GUIDANCE_CARD.md
docs/design/audits/CONTEXT_GUIDANCE_CARD_INTEGRATIONS_AUDIT_2026_07.md
docs/design/README.md
docs/design/DESIGN_SYSTEM.md
docs/design/KAORI_DESIGN_SYSTEM.md
```

## Guardrail

Added:

```text
tests/ui/test_information_guide_card_contract.py
```

The guardrail prevents:

- numbered Connection Type or contract reference items;
- missing item icons;
- using Information Guide Card for ordered flows;
- returning Connection Type Guide to generic page-local markup;
- removing the standard from Design System documentation.

## Result

KAORI now distinguishes between **ordered operational guidance** and **non-sequential reference guidance**. Connection type and contract information are easier to scan, each item has a meaningful visual anchor, and numbering is reserved for genuine order.
