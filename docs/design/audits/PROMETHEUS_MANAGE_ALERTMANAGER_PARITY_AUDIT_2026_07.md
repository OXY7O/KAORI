# Prometheus Manage and Alertmanager Parity Audit — July 2026

## Scope

Reviewed the registered Prometheus manage workspace against the Alertmanager reference implementation across:

- Configuration;
- Validation & Capabilities;
- Runtime & History;
- Scope & Resolution;
- lifecycle routes and partial rendering.

## Findings

### Separate configuration flow

Prometheus exposed an edit route and previously encouraged a separate edit page. This split the manage workflow and differed from Alertmanager, where configuration is edited inline.

### Incomplete capability presentation

Prometheus stored rich metric, label, query, retention, and module-readiness evidence, but the manage workspace did not consistently expose the complete technical contract. Before first validation, the capability list could disappear entirely.

### Runtime implementation drift

Prometheus had provider-local runtime markup and did not consistently share the Alertmanager Health Interpretation, diagnostic hierarchy, or observation presentation.

### Scope management drift

Prometheus primarily displayed bindings and delegated management elsewhere. It did not provide the same inline binding creation and effective-source decision evidence available in Alertmanager.

### Context drift in partial responses

Full-page and HTMX responses could build different context sets, making lifecycle URLs or scope information vulnerable to missing template dependencies.

## Implemented correction

### Configuration

- Prometheus instance detail accepts `GET` and `POST`.
- Configuration is edited inline in the Configuration tab.
- The legacy `/edit` GET route redirects to `#configuration`.
- Existing passwords and bearer tokens may remain blank during an edit.
- Labels use `Request Timeout`, `Verify TLS Certificate`, and `Allow KAORI to Use This Connection`.
- Configuration Flow uses the primary Info Flow standard.

### Validation & Capabilities

- The complete registered Prometheus capability catalog is always rendered.
- Unvalidated capabilities display `Not Observed` rather than being omitted.
- Each capability exposes technical evidence, query/API probe, success criteria, required configuration, operational impact, source owner, dependent modules, sub-checks, and remediation.
- Operational Domain Readiness is separated from capability evidence.
- Full Validation refreshes the same technical workspace through HTMX.

### Runtime & History

- Runtime uses the same summary row and shared Health Interpretation as Alertmanager.
- Diagnostic Pipeline presents ordered technical checks, evidence, duration, and next action.
- Runtime history shows health, readiness, score, latency, trigger, capability changes, and state transition.
- Pagination follows the global default of five with `5 / 10 / 25 / 50` options.

### Scope & Resolution

- Scope bindings are listed and removable inside the manage tab.
- Create Binding is available in the right-side column.
- Duplicate mappings and conflicting enabled primary sources are rejected server-side.
- Effective Source Resolution is shown per analytics consumer, including selected source, candidates, role, priority, required capabilities, decision reason, missing technical capabilities, and missing binding coverage.
- Instance deletion remains blocked until all bindings are removed.

### Route and rendering resilience

- Full-page and HTMX partials use one detail-context builder.
- Lifecycle URLs are resolved defensively outside Jinja.
- Canonical integration state is synchronized after Test Connection, Full Validation, and Runtime Refresh.
- Generic validation failures are handled without rendering an HTTP 500 page.

## Final parity contract

Prometheus and Alertmanager now share:

- the same four-tab manage architecture;
- inline Configuration;
- peer-level Violet summary cards;
- primary Info Flow;
- technical capability detail;
- Health Interpretation and Runtime History;
- inline Scope & Resolution;
- governed destructive lifecycle.

Provider-specific terminology and evidence remain intentionally different.
