# KAORI Core Workspace Lock Audit — 2026-08-07

## Scope

Reviewed and revalidated:

- Welcome
- Kubernetes Inventory
- Kubernetes Analytics
- Kubernetes Operations
- Kubernetes Governance
- Integrations: Overview, Kubernetes, Prometheus, Alertmanager

The purpose of this audit is stabilization, not another visual redesign. Existing documented KAORI design decisions are treated as product contracts.

## Findings and Corrections

### High-priority regressions corrected

- Provider detail pages had recreated page-local framed tablists. Kubernetes, Prometheus, and Alertmanager now call the shared `framed_workspace_tabs` component.
- Several Integration validation surfaces used inline progress width styles. Dynamic percentages now use `components/progress_bar.html`.
- Integration pages contained raw Slate palette utilities and page-local semantic border utilities. Identity and surfaces now use KAORI tokens; semantic state remains in semantic background/text.
- The Kubernetes minimum-validation RBAC example still listed cluster-wide `secrets` read access. The baseline example now excludes Secrets and preserves the governed namespace-scoped Secret access boundary.
- Analytics Top Consumer surfaces had arbitrary 10/11 px typography and a copied standard shell. They now use the documented typography scale and neutral canonical surface treatment.
- The shared operational toast carried an inline timer transform. Timer animation is fully JavaScript-owned, keeping the template free of inline styles.
- The Node Inventory verifier still required an old inline singular/plural expression after pagination moved to the canonical shared resource-name macro. The verifier now locks the shared pagination ownership instead of the obsolete implementation detail.

### Legacy / dead / wrapper review

The existing core cleanup verifier confirms that reviewed Welcome, Inventory, Operations, and Governance paths do not reintroduce known compatibility wrappers such as the old topology bootstrap, dashboard snapshot wrapper, analytics cache wrapper, generic inventory detail wrapper, or Secret operation routes wrapper.

Repository-wide reachability still identifies two unrelated modules outside this lock scope:

- `app/knowledge/remediation_workflow.py`
- `app/users/identity.py`

They are intentionally not removed by this patch because their ownership belongs to the later Intelligence and Identity reviews. They are not imported by the locked workspaces.

### Bounded style debt

The repository already has a style-debt baseline for some shared/domain-local component geometry (for example existing semantic-border and copied-surface candidates). This audit does not silently erase that history or raise the ceiling. The new core workspace lock adds a stricter guard against the high-risk drift that causes large redesigns: raw palette colors, raw hex, arbitrary text sizes, inline styles, inline DOM handlers, page-local workspace tablists, compact rounded pills, known obsolete paths, and RBAC regression.

Future cleanup may reduce the bounded baseline, but no locked workspace may increase it without an explicit design-system change.


### Final refinement: Kubernetes Topology canvas contract

- A `2xl` breakpoint regression had made Display Controls and Topology Details persistent columns, shrinking the graph even on wide screens.
- The canonical contract is restored to canvas-first behavior at every breakpoint: Controls is a left overlay drawer, Details is a right overlay drawer, and resource/relationship selection opens Details on demand.
- Shared visualization geometry, Topology JavaScript, documentation, and contract tests now all enforce the same rule so the persistent three-pane layout cannot silently return.

## Lock Decision

The reviewed workspaces are considered **design-contract locked** after this patch when the scoped verifier and domain contract tests pass. Further work should prefer small defect fixes and content/data changes over structural redesign.
