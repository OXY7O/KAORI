# Integrations Title Case Audit — July 2026

## Scope

This audit covers user-facing semantic labels in the KAORI integrations domain:

- Integrations Overview
- Kubernetes Integrations
- Prometheus Integrations
- Alertmanager Integrations
- Prometheus connection workspaces
- Alertmanager connection workspaces

The review includes headings, form labels, filter labels, table headers, compact information titles, Hero context titles, and short operational labels. Explanatory prose, helper text, placeholders, validation messages, and technical identifiers remain sentence case or retain canonical casing.

## Standard Applied

Use Title Case for:

- page, section, card, modal, drawer, and expandable titles;
- form and filter labels;
- table headers;
- compact information-card titles;
- short operational labels that function as titles;
- Info Flow titles and step titles.

Use sentence case for:

- descriptions;
- helper text;
- empty and error messages;
- boundary explanations;
- instructional prose.

Preserve canonical technical casing for names such as Kubernetes, Prometheus, Alertmanager, API, HTTP, TLS, OAuth, OIDC, GitHub, and KAORI. Dynamic identifiers must not be passed through a mechanical `title` filter.

## Naming Correction

`Alertmanager Scope & Workflow` was renamed to `Alertmanager Registration Flow` because the component explains the registration sequence, not scope configuration itself.

## Results

- 37 integration-domain templates reviewed.
- 25 templates required semantic casing changes.
- Register Alertmanager Instance field labels now include `Instance Name` and `Connection Type`.
- Prometheus and Alertmanager registry filter labels use `Search Connection`, `Readiness`, and `Compatibility`.
- Table headers and compact titles across Overview, Kubernetes, Prometheus, and Alertmanager were normalized.
- Descriptive prose and technical values were intentionally preserved.

## Guardrail

`tests/ui/test_integrations_title_case_contract.py` prevents known regressions and scans static semantic tags for sentence-case labels in the audited integration templates.
