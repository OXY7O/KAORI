# KAORI Hero Context Semantic Alignment — November 2026

Authority: #5394, #572, current HERO.md v1.9 and the canonical Hero verifier. This is a review-only source migration record, not an authenticated Visual QA acceptance or protected staging admission.

## Implemented review slices

| Issue | PR | Scope |
|---|---|---|
| #5398 | #5400 | Shared status/accessory decision rule, exact destination registry and Infrastructure Automation pilot |
| #5401 | #5402 | Object Storage and Source Control navigation, qualified dynamic observability destinations |
| #5406 | #5407 | 26 Kubernetes Dashboard/Inventory/Operations/Governance/Tenant/Analytics templates |
| #5408 | #5409 | Six Registry navigation consumers, Secrets & PKI qualification, Alert Intelligence navigation |
| #5410 | #5411 | Integration portfolio, domain, provider frontpage/detail/registration/edit and OOB status parity |
| #5412 | #5413 | Kubernetes Administration control status, Account overview lifecycle, OpenBao detail/frontpage |
| #5414 | this PR | Analytics preparation status and source census |

## Scope decisions

- A truthful readiness, lifecycle, evidence or authorization state uses the shared status badge. A scope/identity-only context uses the existing context icon; examples include Welcome, normal operational Dashboard scope, Jobs/Data Lifecycle control boundaries, Settings presentation and credential ownership. Do not invent a health state to remove an icon.
- Context-free approved Hero profiles (including read-only Secrets & PKI evidence/registry pages) retain their current composition. Existing provider-specific registration, validation, configuration, return and evidence navigation actions are not Integration landing navigation.
- Canonical Integration destination registry, explicit permission decisions and blocked setup ownership are described in HERO.md. Ansible/Vault/Alertmanager retain exact provider names where the destination is provider-specific. Storage Inventory navigation is not Integration navigation.

## Source census and qualification

Run the existing verifier in the checked-out review revision:

```bash
python scripts/verify_hero_component_standard.py --context-census
python scripts/verify_hero_component_standard.py
````

The optional census emits deterministic source paths, macro names/line numbers, shared provider wrapper references, static Integration URL candidates, explicit endpoint declarations and permission-expression presence. A raw/indirect destination flag is a review candidate, not an assertion that the link is in the Hero; the same template may contain below-Hero navigation. It does not evaluate dynamic branches, Jinja includes, route activation, authorization, data quality, or visual layout. Review each candidate against the route/state matrix, then run existing Hero, family, dark-mode, Developer Check, Full Admission and authenticated desktop/mobile Visual QA. No runtime PASS or exhaustive active-route classification is implied by the source changes alone. #5394 remains open until qualification and remaining discovered drift are dispositioned.
