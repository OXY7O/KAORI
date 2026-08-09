# KAORI Login Visual Refinement Audit

Date: 09 August 2026  
Scope: unauthenticated login presentation only.

## Outcome

The login retains the compact split-screen architecture. The left brand panel now uses a dedicated KAORI Operations Fabric illustration instead of the legacy decorative node/line motif. The visual represents infrastructure inputs converging on a governed operational core and producing observable, controlled, and auditable outcomes.

This batch intentionally does not change authentication routes, provider behavior, session handling, database models, RBAC, or login-audit semantics. Authentication security hardening remains a separate change set after visual review against the current Auth source.

## Presentation Contract

- Global KAORI identity only; no provider or workspace catalog before authentication.
- Primary value statement: **Operate with clarity.**
- Supporting copy remains short and infrastructure-oriented.
- Capability cues remain Visibility, Control, Intelligence, and Assurance.
- Violet/lavender are the primary brand accents; surfaces remain deep neutral.
- The Operations Fabric is decorative (`alt=""`, `aria-hidden="true"`) and does not communicate authorization state.
- The right login form stays compact for a 14-inch laptop; the visual refinement must not increase input or submit-button height.
- Responsive behavior hides the rich left-panel content below the split-layout breakpoint so authentication remains the mobile priority.

## Files

- `app/static/images/kaori-login-operations-fabric.svg`
- `app/static/css/auth-login.css`
- `app/templates/auth/partials/_brand_panel.html`
- `tests/contracts/auth/test_login_visual_refinement_contract.py`

## Security Boundary

The SVG is static, contains no script or external resource references, and is presented as decorative content. The login page still must not expose provider payloads, account existence, role state, or authentication internals through presentation copy.

## Follow-Up

After visual acceptance, audit the current Auth implementation before modifying security behavior. The next batch should cover safe redirect handling, authentication throttling, session fixation/rotation, cookie policy, inactive/deleted fail-closed behavior, external-provider callback controls, and password-reset session invalidation.
