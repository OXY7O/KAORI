# KAORI Integrations Final Lock Audit — 2026-08-08

## Decision

Integrations is approved as a locked KAORI workspace baseline after the final refinement and cleanup pass.

The audit covers Integration Overview, Runtime Overview, Kubernetes, Prometheus, Alertmanager, provider capability registries, runtime evidence, configuration, bindings/consumers, lifecycle actions, shared dialogs, loading, pagination, dark mode, RBAC boundaries, and shared operational feedback.

## Final Findings Resolved

### Shared capability/readiness ownership

The last provider drift was removed by making Kubernetes use the same shared capability-readiness component already used by Prometheus and Alertmanager. Operational Gate, Evidence Boundary, Next Operational Action, progress treatment, status placement, spacing, and dark-mode behavior now have one presentation owner.

### Real loading behavior

Kubernetes Capability Registry, PromQL Capability Registry, and Alert Management Capability Registry use real HTMX requests for search/filter/page-size/pagination interactions and one shared loading indicator each. Synthetic timer-based loading feedback is prohibited.

### Runtime evidence hierarchy

Provider runtime workspaces use concise current-state evidence while immutable technical detail remains behind Recent Runtime Observations -> View More. Runtime Observation detail uses the shared record-detail modal and does not duplicate the same failure text in multiple blocks.

### Configuration symmetry

Prometheus and Alertmanager Configuration Decision intentionally remain side panels because the configuration form is the active working surface. Shared geometry now keeps left/right boundaries aligned and the Save Changes action is an embedded footer rather than a floating nested card.

### Binding semantics

The provider tab badge counts registered `binding_rows`, not a stale `scope_bindings` fallback. A disconnected source therefore retains its registered binding count while Binding Validation and Effective Resolution can correctly show blocked/non-operational states.

### Kubernetes RBAC boundary

The baseline Full Validation ClusterRole excludes Secrets. Optional Secret read access remains a separate namespace Role + RoleBinding under its own modal tab. The core UI lock verifier was corrected so it protects the baseline without falsely rejecting the approved namespace-scoped optional boundary.

### Operational toast regression

The shared operational-toast countdown no longer contains inline transform style. Timer initialization and animation remain JavaScript-owned through `operational_toasts.js`, restoring the locked inline-style rule.

### Legacy/dead presentation cleanup

Static reference review confirmed two old templates had no active owner and represented retired interaction architectures:

- `app/templates/integrations/partials/_runtime_detail_content.html` — old inline Runtime Overview expansion;
- `app/templates/prometheus/partials/_analytics_readiness.html` — old provider-local Analytics readiness presentation.

Both are removed and registered as obsolete paths so they cannot silently return.

## Frozen Exceptions

The audit intentionally keeps one major layout exception:

- Configuration uses a compact side decision rail beside the working form.

Validation, Runtime, Bindings, Capability Readiness, Inventory/Lifecycle decisions, and Runtime Overview do not use persistent side decision rails.

Technical commands, PromQL, API requests, and YAML may use bounded internal scrolling when preserving exact syntax is operationally necessary. Canonical registries themselves must not force the desktop workspace to scroll horizontally.

## Verification Gates

Final acceptance requires all of the following:

```text
Integration contracts                     PASS
Integrations final-lock verifier          PASS
Core workspace UI lock                    PASS
Core workspace legacy cleanup             PASS
Dark mode standard                        PASS
Python syntax                              PASS
Integration templates: raw color/style    0 violations
```

The repository-wide UI style verifier can still surface pre-existing unrelated Notifications/Reports debt; no new Integration-specific debt is accepted by this lock.

## Post-Lock Policy

Future Integration changes should be treated as minor defect fixes, provider-data/capability changes, backend improvements, or security fixes. Reopening major layout or interaction architecture requires an explicit lock-contract change with documentation, verifier, and regression-test updates.
