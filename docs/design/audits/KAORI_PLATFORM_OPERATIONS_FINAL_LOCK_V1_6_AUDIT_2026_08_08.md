# KAORI Platform Operations Final Lock v1.6 Audit — 2026-08-08

## Decision

Secret Reveal v1.6 is accepted as a bounded refinement over v1.5.

## Findings Closed

- A Namespace could be visibly policy-enabled in Platform Operations while Protected Reveal only showed an empty disabled Cluster selector. The runtime behavior was secure and correct, but the distinction between Namespace Policy and the deployment-level global kill switch was not explicit enough.
- Protected Reveal now states the exact activation dependency: `KUBERNETES_SECRET_REVEAL_ENABLED=true` plus KAORI restart/redeployment.
- The page exposes configured policy-enabled Namespace count while the global gate is disabled, making configuration evidence visible without weakening the gate.
- `get_reveal_clusters()` still returns no selectable target while the global gate is disabled. Once enabled, selection still requires cluster readiness and configured enabled Namespace policy.
- The target workspace still verifies configured Namespaces live and does not require broad Namespace LIST permission.
- Administration Readiness Controls/Kubernetes Boundary and Protected Reveal main/context rail now use explicit stretch geometry for symmetric desktop boxes.
- Contextual flow copy was shortened to prevent the right rail from visually dominating the operational workspace.
- Dark-mode semantic surfaces remain unchanged.

## Security Conclusion

No authorization boundary was removed or relaxed. v1.6 improves diagnosis and geometry only; the deployment-level kill switch remains independent from Namespace Policy configuration by design.
