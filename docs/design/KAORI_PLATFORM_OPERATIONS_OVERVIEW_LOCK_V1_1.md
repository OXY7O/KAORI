# KAORI Platform Operations Overview Final Lock v1.1

v1.1 supersedes Overview v1 with a denser KAORI control-plane presentation while preserving its read-only, permission-aware, DB/lightweight composition contract. The active identity wording is reconciled with Hero v1.9 / #749: domain context stays in the eyebrow and the H1 names the current destination without repeating that context.

## Locked presentation

- Hero identity: eyebrow **Operations Center** with H1 **Overview**, following the canonical Hero v1.9 non-redundant identity rule.
- Hero boundary copy: **Read-only overview; changes stay in each workspace.**
- Main section: **Workspace Posture**, with one compact control card per permitted workspace.
- Three-workspace users receive a balanced three-column layout; one/two-workspace users receive matching adaptive columns without an intentional empty quadrant.
- Each card owns one icon, one semantic status, three compact metrics, one ownership boundary label, and one navigation CTA.
- Secondary section: **Operating Boundaries** for Execution Evidence, Lifecycle Governance, and Protected Administration.
- **Workspace Posture contextual Guide:** the section header places one canonical shared `info_tip.render(..., variant='guide')` immediately after the authoritative `overall_status_label` / `overall_status_tone` indicator through `operational_section.render(header_badge=...)`. It explains scope: Jobs & Executions owns canonical execution and worker evidence; Data Lifecycle owns retention and verified archive-first cleanup; Kubernetes Administration owns readiness/reveal policy while Secret values stay in Secret Management and live access checks occur at execution. No extra status evaluation, live provider requests, action or mutation.
- **Operating Boundaries one-line copy:** the three `boundary_description` values are compact, domain-owned one-sentence descriptions in `overview/presentation.py`: Jobs queues/retries/execution evidence, Data Lifecycle retention/verified archives, and Kubernetes readiness/reveal access. On normal desktop each is one line using existing responsive `lg:truncate` with an identical native `title` fallback; mobile may naturally wrap. The full authority distinctions remain in the contextual Guide, while essential status/boundaries remain visible in each domain workspace. Preserve permission-scoped 1/2/3 card geometry; do not introduce page-local CSS, hardcoded status or artificial information loss.
- **Operating Boundaries are permission-scoped** and render only the workspaces visible to the current user; inaccessible control planes must not be advertised from the Overview.
- Overall posture precedence is **critical → warning → configuration review → active → ready**. Unknown/setup states must never collapse into a false `Ready` posture.
- Kubernetes Administration mirrors its authoritative global feature gate: a disabled global reveal gate is a review state even when no namespace policy has been enabled yet.
- No mutation form, POST, background probe, or alternate source of truth may be added.
- Navigation menu label and page/domain title for the Kubernetes workspace use the full **Kubernetes Administration** wording.
