# Intelligence domain

Intelligence is KAORI's central rule, recommendation, and alert-enrichment domain.
Analytics workspaces consume this domain instead of maintaining independent legacy
recommendation logic.

## Responsibilities

- `catalog.py`: canonical rule definitions and P1-P4 severity semantics.
- `recommendation_engine.py`: rule evaluation and recommendation construction.
- `service.py`: public use cases, filtering, and orchestration.
- `routes.py`: HTTP/HTMX boundary.

Rules must identify source, domain, impacted assets, evidence, and remediation.
Imported and internal rules share one catalog contract. Do not embed page-specific
recommendation rules directly in analytics routes or templates.

## KAORI Violet presentation standard

All Intelligence workspaces use the KAORI Violet Infrastructure design system. Recommendations, Catalog, and Alert Intelligence share a solid violet hero, a right-side posture card, tokenized surfaces and borders, `rounded-xl` sections, `rounded-lg` internal object blocks, violet focus states, and compact rectangular status/metadata labels. Semantic green, amber, red, cyan, and slate remain reserved for operational state, priority, or risk; decorative blue gradients and literal slate surfaces must not be reintroduced.
