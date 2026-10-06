# KAORI Platform Operations Final Lock v1.7 Audit — 2026-08-08

## Decision

Secret Reveal returns to natural, content-driven side-panel height. Equal-height forcing introduced in v1.6 made compact contextual cards consume empty vertical space and reduced visual balance. The deployment-level global kill switch remains mandatory, but its activation instruction is moved from a long Cluster-field helper into a compact `Activation Tip` callout.

## Verified Boundaries

- Global Protected Reveal enablement remains independent from Namespace Policy.
- Configured enabled Namespace evidence remains visible when the global gate is off.
- Cluster selector remains disabled while the deployment flag is off.
- Activation copy identifies `KUBERNETES_SECRET_REVEAL_ENABLED=true` and restart/redeploy requirements.
- Protected Reveal and Platform Operations Secret Reveal panels use natural height rather than forced stretch geometry.
- Shared Context Rail returns to its canonical start-aligned geometry.
- Existing compact flow copy and neutral-first dark-mode surfaces remain intact.
- No authorization, database, or migration behavior changes.
