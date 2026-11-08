# Identity Providers Application Workspace

`app/access/identity_providers` owns the authenticated administrative workspace for external identity providers. It does not implement authentication protocols and it does not own user lifecycle mutations.

Canonical layering:

```text
Access / Authentication
  -> Identity Provider
      -> provider_key
      -> adapter_key
      -> admission policy / capabilities
      -> identity projection
```

Ownership:

- `routes.py`: administrative HTTP boundary and tab routing.
- `forms.py`: provider-neutral common form plus adapter-profile fields.
- `service.py`: registry/filter/pagination/presentation composition.
- `provisioning.py`: provider-neutral directory identity projection.
- `provisioning_proof.py`: short-lived signed identity evidence.
- `notifications.py`: operational feedback and Activity Audit integration.

Provider-specific protocol behavior must not be added here. It belongs under `app/access/authentication/identity_provider/providers/<provider>/` or `app/access/authentication/identity_provider/adapters/<adapter>/`.

## Firefox laptop contextual guidance UAT (#2279)

Google OIDC Guidance and Exact Callback URL help use concise copy while the
underlying setup steps and exact generated scheme/host/path/provider-key callback
remain unchanged. The existing Provider/Adapter Boundary text already expresses
a compact one-line statement and is retained. Related Add User provider navigation
copy is covered by bounded User Management issue #2278.

The dynamic registered-account / local break-glass count shown in the operator
screenshot has not been mapped to its committed source owner; it is **not**
silently rewritten or considered fixed. Capture the exact page and source
projection during Dev Container Firefox UAT. Desktop one-line appearance,
responsive/mobile wrapping, keyboard, light/dark and human acceptance remain
PENDING until browser execution; no official admission is implied.

## LDAP selector feedback UAT (#2280)

Source-controlled `ldap_directory` remains an enabled *configurable choice*
while provider authentication itself is independently controlled by the existing
enabled flag, adapter validation and TLS/secret-reference gates. The Add
Identity Provider selector uses native radio + matching label; the existing
selection controller now updates the nested visible **Select / Selected** badge
from the radio checked state, since nested badge children cannot use
`peer-checked` directly. LDAP configuration form, credentials, permission
checks and server-side validation have not changed.

The operator reported that LDAP was not selectable; the source proves a
visual-state feedback defect but does **not** prove the reported functional
failure has been resolved. Run Firefox Dev Container pointer and keyboard
selection, panel-field enablement, form submission with safe test fixtures,
negative TLS/missing-secret tests and human acceptance. External LDAP
connectivity is separate provider-authoritative evidence. All remain PENDING
until actually executed; official CI/CD and deployment HOLD.

Firefox L13 text budget follow-up: retain the exact generated callback URL below
the header; keep the summary caption short. Google authenticates users, while
KAORI's role and lifecycle governance remains authoritative in the existing
identity-projection/workflow documentation. Runtime single-line QA pending.

### Repeat Firefox UAT: LDAP card does not select (#2280)

A further operator screenshot confirmed GitHub stayed checked and the LDAP
configuration did not appear when trying to select the LDAP / Active Directory
card. The previous badge-state change was insufficient. The provider choice
still uses the same catalog-derived native radio, sibling label, accessible
name, keyboard semantics and existing `change` controller; the native input
now fills the card as an invisible pointer hit target. This removes reliance
on forwarded clicks through the label in Firefox. It changes only the input
hit area, not `disabled` gates, provider type, catalog, RBAC, LDAP credentials,
TLS policy, JIT, or submission.

A focused isolated Playwright UI regression exercises pointer and keyboard
selection transitions and panel/field visibility without connecting to LDAP
or submitting any provider changes. The operator's real Dev Container Firefox
test and human acceptance still govern UAT PASS; official CI/CD stays HOLD.

### Root-cause fix: Lucide replaced the LDAP radio (#2280)

Actual Firefox DOM evidence exposed an SVG `lucide-log-in` carrying
`type="radio"` and `data-provider-key="ldap_directory"` with only two native
provider inputs remaining. This traced to a collision: every provider radio
had `data-provider-icon` metadata while `identity_provider_form.js`
selected the **first** `[data-provider-icon]` as an icon display target.
The controller added `data-lucide` to the LDAP input; the bundled Lucide
renderer replaced the input with an SVG. The earlier badge-only and
full-card CSS changes did not address this destructive DOM mutation.

The source-controlled provider option now holds icon metadata under
`data-provider-option-icon`, separate from
`data-provider-display-icon` on the actual SSO configuration icon.
The controller selects the displayed icon within its configuration panel
on each update because Lucide replaces the original `<i>` with `<svg>`.
It never assigns `data-lucide` to a radio input. The existing Playwright
browser test now loads the real vendored Lucide renderer and asserts all
three native provider radios remain present after initial render, LDAP
selection and keyboard switching. No credential, provider integration,
authorization, admission, TLS or database functionality changed.

The operator's real Dev Container Firefox result, CI and human
acceptance remain PENDING/NOT RUN until executable evidence is recorded.
Official staging/deployment/release remain HOLD.

### REVIEW(3) — Header-level input guidance (#2301)

Access Identity Provider Add/Edit now uses one canonical title-adjacent
`info_tip.render(..., variant='guide')` per owning form section:
Provider Identity and State, LDAP Adapter Connection, Directory Identity
Mapping, browser Application, and Admission and JIT Provisioning.
The section Guide consolidates **static input helper copy**, including
directory TLS/service bind/secret handling, escaped directory user filter,
identity mapping, OAuth/OIDC client ID/secret source and non-admin JIT role.
The input labels, placeholders, field validation errors and live dynamic
`data-enabled-copy`, provider-specific `data-admission-help`, JIT-toggle
status, disabled-state notification and security controls remain visible
in their original owning fields. Do not hide mandatory validation or current
provider/admission state in a popover. The existing JS Info Tip controller
owns keyboard/hover/touch and viewport placement. Actual Firefox Lenovo
L13/mobile/light-dark/zoom acceptance remains PENDING until executed.

### REVIEW(3) — Provider Guidance line-density targets (#2279)

Firefox Lenovo L13 review requests **approximately two natural lines**
per browser-provider setup-step description and **one line** for each
credential-ownership/admission note. The GitHub OAuth and Google OIDC
four-step workflows use concise, complete guidance: registration, exact
callback, environment-referenced secret, and explicit non-admin JIT
admission. Provider notes distinguish external authentication from KAORI
authorization; the LDAP guidance steps already describe identity mapping.
The shared `info_flow.render()` component and typography remain unchanged.
These are desktop screenshot targets, not forced line breaks, truncation,
font reduction or browser PASS. Real Dev Container Firefox/mobile/zoom/dark
and human acceptance remain PENDING.

### REVIEW(4) — LDAP form columns and mapping placeholders (#2306)

The LDAP User Search Filter and TLS Mode occupy adjacent columns in the
existing `sm:grid-cols-2` configuration grid, reverting to natural
stacking on narrower viewports. On **Add** Identity Provider, attribute
examples `sAMAccountName`, `mail`, `displayName`, and `objectGUID`
are input placeholders rather than WTForms-created field values. Their
real configured values must be supplied and validated before LDAP
save/enable; blank mapping attributes still fail existing required-field
validation. **Edit** Identity Provider continues to hydrate actual saved
mapping values from `populate_provider_form()`, never overwrite them
with placeholders. LDAP TLS guards, bind secret reference and
`{query}` escape remain unchanged. Real Firefox Dev Container UAT,
validation-negative testing, human acceptance and official admission
are separate, pending evidence.

### REVIEW(4) — Provider Guidance compact headings (#2279)

Directory, GitHub and Google Guidance headers now use short descriptions
identifying external sign-in and KAORI's local access decision. Detailed
four-step provider onboarding and credential-authority notes remain in the
existing Info Flow component. One-line appearance is a Firefox Lenovo L13
visual target; mobile text may wrap naturally. No forced nowrap/clipping,
policy change, provider API work, or secret access. Post-fix Firefox UAT
and human acceptance remain PENDING; official CI/CD admission HOLD.
