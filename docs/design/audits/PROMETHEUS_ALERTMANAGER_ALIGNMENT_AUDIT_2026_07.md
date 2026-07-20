# Prometheus and Alertmanager Workspace Alignment Audit — July 2026

## Scope

This audit covers:

- Prometheus Integrations landing and registry;
- uncovered operational scope guidance;
- Register and Edit Prometheus Connection;
- Prometheus instance lifecycle navigation;
- Prometheus route references used by templates;
- alignment with the established Alertmanager registration and provider workspace patterns.

## Findings

### Duplicate landing actions

`Register Connection` appeared in both the Hero Context Panel and registry header. `Instances & Bindings` appeared in the integration overview header and registry header. Repeating the same actions weakened hierarchy and made the page feel different from Alertmanager.

### Hero context was too verbose

The Prometheus Hero Context Panel contained an extra explanatory paragraph and page-local metric markup. Alertmanager already established the preferred compact pattern: posture title, semantic status, two shared metrics, and one action.

### Uncovered-scope action used a page-local button style

`Register & bind` did not follow the global primary button height, typography, focus treatment, or Title Case contract.

### Registration guidance mixed responsibilities

The Prometheus registration page used one broad flow plus a local `Connection Versus Capability` information box. It did not explain compatibility detection choices clearly and did not provide the standardized `After Registration` guidance used by Alertmanager.

### Related Analytics Workspace stretched vertically

The shared Related Page Card used full-height behavior and `mt-auto`. Inside the tall registration form grid, this could stretch the related card far beyond its content.

### Delete URL could break page rendering

The instance detail template built `prometheus.delete_instance` directly. A partial deployment where the template was updated before the route was registered raised `BuildError` and made the complete instance page unavailable.

## Implementation

### Landing action ownership

- Hero owns the single `Register Connection` primary action.
- Registry owns one secondary `Manage Scope Bindings` action.
- Integration Overview has no duplicated action.

### Hero alignment

Prometheus now uses the same compact context structure as Alertmanager:

- Integration Posture;
- Connection Readiness and Bindings;
- semantic posture label;
- Ready and Bindings metrics through shared Hero helpers;
- one Register Connection action;
- no explanatory paragraph inside the context panel.

### Uncovered operational scopes

The action now uses the global primary action geometry and reads `Register & Bind` in Title Case.

### Registration workspace

The Prometheus page now follows the Alertmanager information hierarchy:

1. primary Prometheus Registration Flow;
2. non-sequential Compatibility Detection guide;
3. ordered After Registration guidance;
4. optional Initial Scope Binding context;
5. Related Analytics Workspace.

Automatic and manual dropdown values are concise and technically explicit:

- `Automatic — Direct Prometheus`;
- `Manual — Prometheus-Compatible Gateway`;
- `Prometheus v2`;
- `Prometheus v3`.

### Related Page Card height

The shared component now uses intrinsic content height and `mt-6` action spacing. It does not stretch to match a taller adjacent form.

### Route resilience

The delete route has an explicit endpoint name. The instance detail route builds the lifecycle URL through `_optional_endpoint_url()`. If a partial deployment has not registered the endpoint, the page renders a disabled `Delete Unavailable` state and logs the deployment inconsistency instead of raising `BuildError` from Jinja.

A static regression test also checks every `prometheus.*` endpoint referenced by Prometheus templates against the handlers declared in `app/prometheus/routes.py`.

## Regression Contract

- one Register Connection action on the provider landing page;
- one Manage Scope Bindings action on the provider landing page;
- no duplicate action in Integration Overview;
- Prometheus Hero Context follows the Alertmanager compact structure;
- Compatibility Detection uses Information Guide Card;
- After Registration uses ordered Context Guidance Card;
- Related Page Card uses intrinsic height;
- instance detail never builds an optional delete endpoint directly in Jinja;
- every Prometheus template route reference maps to a declared Prometheus handler.
