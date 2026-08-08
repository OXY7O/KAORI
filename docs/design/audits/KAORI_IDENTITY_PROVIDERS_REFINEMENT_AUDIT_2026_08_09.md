# KAORI Identity Providers Refinement Audit — 2026-08-09

## Scope

Identity Providers remains under the Access control-plane composition while `app/users` owns provider administration and identity projection, `app/auth` owns LDAP/OIDC/OAuth protocol behavior, and `app/rbac` owns authorization. This review does not final-lock the Access domain.

## Accepted Refinements

- Replaced the custom Identity Providers hero rail with the shared Inventory-style `page_hero.context_card()` grammar.
- Added Provider Registry Overview with independent configuration, enablement, LDAP, and SSO posture.
- Added explicit Credential Ownership, Runtime Validation, Identity Projection, and Authorization Boundary evidence.
- Rebuilt the provider list as a shared KAORI registry with Search / Provider Type / Provider State filters, a correctly spanning shared HTMX loading bar, standard title cells, semantic labels, and expand-below-row details.
- Provider detail exposes credential environment references only; secret values remain outside provider records.
- Validation remains an on-demand action. The UI does not invent a durable `Last Validated` or `Validated` provider state because no such evidence is persisted yet.
- Kept Directory Provisioning as the LDAP child workflow and redesigned it as a full-width operational workflow with LDAP/provider posture, the local-role authorization boundary, four controlled provisioning steps, and a direct action above the Provider Registry.
- Removed the Identity Providers index right rail: Authentication Boundary and provider-family guidance are consolidated into Provider Registry Overview instead of repeated side documentation.
- Standardized LDAP, Google OIDC, and GitHub OAuth guidance on the same always-visible `info_flow` grammar used by Role Assignment Flow. The Technical Runbook is no longer expandable and remains visible as a compact reference card.
- Added live draft testing on Add/Edit Identity Provider. `Test Connection` for LDAP and `Test Configuration` for SSO validate current form values without saving the provider or inventing durable validation posture.
- Normalized provider-form field typography to the standard KAORI sans-serif input treatment; monospaced typography remains reserved for actual technical values such as callback URLs and runbook paths.
- Upgraded Provider Registry to the full shared KAORI table contract, including the standard title cell, top-right matching count, full-width shared loading bar, server-side pagination, default Rows=5, Previous/Next, numeric pages, and filter-preserving HTMX navigation.
- Standardized provider form hero composition and retained the shared Access sticky right-rail contract (`xl:sticky xl:top-5`) for Add/Edit forms only.

## Security / Correctness Boundary

`Configured`, `Enabled`, and runtime validation are deliberately separate concepts. Provider authentication does not grant KAORI authorization; external identities still require a KAORI account projection and local role assignment.

## Open Before Identity Providers Final Lock

- Decide whether durable provider-validation evidence is required before showing historical validation posture.
- Review provider-type mutability after real UI usage; no URL namespace cutover is required for this refinement.


## v1.16 Directory Provisioning flow refinement

- Replaced the 2x2 arrow-card Directory Provisioning diagram with the shared compact `operational_point_flow` lifecycle path.
- The workflow is now a four-stage read path without zig-zag arrows or per-step cards: Validate Provider → Find Identity → Assign Role → Provision Account.
- The point-flow component now chooses a stable 3/4/5-column desktop grid from the number of stages so four-stage workflows do not leave an empty fifth column.
- Directory Provisioning keeps the compact four-step lifecycle path without the redundant “Credentials Stay Directory-Owned” side label; credential ownership remains documented in the surrounding provider boundaries.
