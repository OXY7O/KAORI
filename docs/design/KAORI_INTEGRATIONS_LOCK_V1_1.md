# KAORI Integrations Lock v1.1

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Configuration Decision rail density guidance in `KAORI_INTEGRATIONS_LOCK_V1.md`

## Scope

v1.1 keeps the frozen Integration workspace architecture, shared provider configuration rail, equal-height left/right configuration geometry, provider validation contracts, runtime evidence, bindings, and dark-mode rules. It reopens only the observed Prometheus Configuration Decision rail density issue where the right rail stretched correctly but left excessive unused vertical space.

## Configuration Decision rail density

1. **Symmetric configuration geometry remains frozen.** Provider configuration pages keep `items-stretch`; the shared Configuration Decision panel keeps full-height/self-stretch behavior so the right rail aligns with the working form.
2. **Empty rail capacity must become decision support, not filler.** The shared side panel accepts optional provider-specific `Operational Effects` and `Validation Boundary` evidence.
3. **Controlled Flow is compact.** Configure, Validate, Observe, and Resolve use a 2x2 compact card grid rather than a sparse vertical timeline.
4. **Prometheus uses both optional evidence blocks.** Operational Effects explains Save Changes, Test Connection, Full Validation, and Consumer Use. Validation Boundary maps Transport Check, Capability Contract, Consumer Eligibility, and Operational Use to their authoritative action/gate.
5. **Consumer Boundary is concise.** Prometheus remains authoritative for metric query execution while KAORI governs source selection, validation evidence, bindings, and consumer eligibility.
6. **Alertmanager remains backward compatible.** The shared macro parameters are optional; Alertmanager continues to use the canonical rail without provider-specific Prometheus evidence.
7. **Dark mode stays neutral-first.** Added cards use semantic KAORI surfaces and borders; no raw palette, hardcoded white, or oversized brand-filled panels are introduced.
8. **No runtime semantics change.** This refinement is presentation/evidence density only. Provider connection, readiness, validation, and binding logic are unchanged.

## Enforcement

```bash
python scripts/verify_integrations_final_lock.py
pytest -q tests/contracts/integrations/test_prometheus_configuration_decision_density_contract.py
pytest -q tests/contracts/integrations
python scripts/verify_dark_mode_standard.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_python_syntax.py
```
