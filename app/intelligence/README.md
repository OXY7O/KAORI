# Intelligence domain

Intelligence is KAORI's central rule, recommendation, alert-enrichment, and
immutable decision domain. Analytics workspaces consume this domain instead of
maintaining duplicate page-specific recommendation logic.

## Responsibilities

- `catalog.py`: canonical rule definitions and P1-P4 severity semantics.
- `recommendation_engine.py`: rule evaluation and recommendation construction.
- `service.py`: public use cases, filtering, and recommendation orchestration.
- `workflow.py`: immutable decision approval and rejection transitions.
- `routes.py`: domain-owned HTTP/HTMX surfaces for Recommendations, Alert Intelligence, and Rule Catalog.

Rules must identify source, domain, impacted assets, evidence, and remediation.
Imported and internal rules share one catalog contract. Do not embed page-specific
recommendation rules directly in analytics routes or templates.

## Cross-domain automation orchestration

The **Automation Control Center** is intentionally owned by the application layer
under `app/automation_control/`, not by this domain. It coordinates read models
and governed commands across Knowledge, Intelligence, Resolver, and Production
Readiness without making those domains import one another. The application layer
may call Intelligence public use cases; Intelligence must not import the
Automation Control package.

Route: `/intelligence/automation-control`

See `docs/architecture/domain-20-automation-control-center-ui.md`.

## KAORI Violet presentation standard

All Intelligence workspaces use the KAORI Violet Infrastructure design system.
Recommendations, Catalog, Alert Intelligence, and the cross-domain Automation
Control Center share a solid violet hero, a right-side posture card, tokenized
surfaces and borders, `rounded-xl` sections, `rounded-lg` internal object blocks,
violet focus states, and compact rectangular status/metadata labels. Semantic
green, amber, red, cyan, and slate remain reserved for operational state,
priority, or risk; decorative blue gradients and literal slate surfaces must not
be reintroduced.

## Intelligence Workspace Presentation

Recommendations, Rule Catalog, Alert Intelligence, and Automation Control use the canonical Intelligence workspace contract documented in `docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md`.

Automation Control mutations are disabled by default. Set `AUTOMATION_CONTROL_MUTATIONS_ENABLED=true` only after validation gates and behavioral tests are complete. The disabled UI state is named **Reserved Plan**; MVP, placeholder, preview-only, and coming-soon labels are not used.
