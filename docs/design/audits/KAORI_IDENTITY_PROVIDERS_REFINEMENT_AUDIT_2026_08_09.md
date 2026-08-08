# KAORI Identity Providers Refinement Audit — 2026-08-09

## Scope

Identity Providers remains under the Access control-plane composition while `app/users` owns provider administration and identity projection, `app/auth` owns LDAP/OIDC/OAuth protocol behavior, and `app/rbac` owns authorization. This review does not final-lock the Access domain.

## Accepted Refinements

- Replaced the custom Identity Providers hero rail with the shared Inventory-style `page_hero.context_card()` grammar.
- Added Provider Registry Overview with independent configuration, enablement, LDAP, and SSO posture.
- Added explicit Credential Ownership, Runtime Validation, Identity Projection, and Authorization Boundary evidence.
- Rebuilt the provider list as a shared KAORI registry with Search / Provider Type / Provider State filters, shared loading bar, semantic labels, expand-below-row details, and standard Rows / Previous / numeric / Next pagination.
- Provider detail exposes credential environment references only; secret values remain outside provider records.
- Validation remains an on-demand action. The UI does not invent a durable `Last Validated` or `Validated` provider state because no such evidence is persisted yet.
- Kept Directory Provisioning as the LDAP child workflow and moved it into a full-width operational strip above the Provider Registry.
- Removed the Identity Providers index right rail: Authentication Boundary and provider-family guidance are consolidated into Provider Registry Overview instead of repeated side documentation.
- LDAP Setup Guidance now opens by default and uses the shared KAORI box-flow component; Google/GitHub guidance and the technical runbook remain collapsed.
- Standardized provider form hero composition and retained the shared Access sticky right-rail contract (`xl:sticky xl:top-5`) for Add/Edit forms only. Add/Edit also supports a non-persistent Test Connection action against the current form values before Save.

## Security / Correctness Boundary

`Configured`, `Enabled`, and runtime validation are deliberately separate concepts. Provider authentication does not grant KAORI authorization; external identities still require a KAORI account projection and local role assignment.

## Open Before Identity Providers Final Lock

- Visual review of Directory Provisioning as the LDAP sub-workspace.
- Decide whether durable provider-validation evidence is required before showing historical validation posture.
- Review provider-type mutability after real UI usage; no URL namespace cutover is required for this refinement.
