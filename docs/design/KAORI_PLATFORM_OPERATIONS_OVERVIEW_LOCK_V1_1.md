# KAORI Platform Operations Overview Final Lock v1.1

v1.1 supersedes Overview v1 with a denser KAORI control-plane presentation while preserving its read-only, permission-aware, DB/lightweight composition contract.

## Locked presentation

- Hero title: **Platform Overview**.
- Hero boundary copy: **Read-only overview; changes stay in each workspace.**
- Main section: **Workspace Posture**, with one compact control card per permitted workspace.
- Three-workspace users receive a balanced three-column layout; one/two-workspace users receive matching adaptive columns without an intentional empty quadrant.
- Each card owns one icon, one semantic status, three compact metrics, one ownership boundary label, and one navigation CTA.
- Secondary section: **Operating Boundaries** for Execution Evidence, Lifecycle Governance, and Protected Administration.
- **Operating Boundaries are permission-scoped** and render only the workspaces visible to the current user; inaccessible control planes must not be advertised from the Overview.
- Overall posture precedence is **critical → warning → configuration review → active → ready**. Unknown/setup states must never collapse into a false `Ready` posture.
- Kubernetes Administration mirrors its authoritative global feature gate: a disabled global reveal gate is a review state even when no namespace policy has been enabled yet.
- No mutation form, POST, background probe, or alternate source of truth may be added.
- Navigation menu label and page/domain title for the Kubernetes workspace use the full **Kubernetes Administration** wording.
