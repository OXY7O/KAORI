# KAORI Authentication Surface Lock v1

Status: **FINAL LOCKED**  
Date: 2026-08-11

## Scope

This lock covers the unauthenticated KAORI authentication presentation surface:

- Login
- Database Setup Required
- `layouts/auth.html`
- Auth-specific first-party CSS/JavaScript required by those surfaces

It does not redesign identity-provider administration, User Management, Roles & Access, Account & Authentication Settings, or provider protocol implementations.

## Locked Presentation Contract

1. Login remains the approved compact split-screen design optimized for a 14-inch laptop.
2. KAORI Violet remains the primary brand/accent language and light/dark mode remains supported.
3. The pre-authentication brand panel stays provider-neutral; it must not reveal enabled internal workspaces, account state, roles, or provider-specific operational details.
4. Username/password controls remain 44 px high with visible labels, autocomplete metadata, CSRF ownership, accessible password visibility control, and a clearly labeled Remember Me control.
5. SSO actions are rendered only for enabled browser providers and propagate only the server-sanitized internal `next` target.
6. Login feedback keeps semantic success/error roles and an `aria-live` region.
7. Database readiness fails closed to the Database Setup Required surface with operator-safe initialization guidance.
8. Auth templates use canonical typography tokens: no arbitrary text sizes/tracking, no `font-extrabold`, no presentation-only uppercase utilities, and no inline DOM event handlers.
9. Password/theme interaction runtime is owned by `app/static/js/auth_login.js`; only the pre-paint theme bootstrap remains inline to prevent theme flash.

### Browser SSO Action Region

The accepted split-screen login remains unchanged when browser SSO is disabled. The SSO action region is conditional and consumes no blank placeholder space when no runtime-ready browser provider exists.

Current supported browser providers are Google OIDC and GitHub OAuth. Their login actions are rendered from the provider registry rather than hard-coded provider branches.

Canonical geometry:

- zero providers: no divider and no SSO action region;
- one provider: one full-width 44 px action;
- two providers: two peer 44 px actions in a two-column row from `sm`, stacked below `sm`;
- additional future browser providers wrap through the same two-column grid;
- provider display names may vary, so button text uses a bounded flexible/truncating span while the full name remains available through accessible label/title text;
- every provider link preserves only the server-sanitized internal `next` target.

The Local Database form remains the primary credential/recovery path and provider actions remain visually secondary to **Sign In**.

### Login Responsive Composition

Laptop browser usage is the primary product target, but Authentication follows the global canonical viewport authority from `tests/ui/conftest.py::CANONICAL_VIEWPORTS`:

| Viewport | Size | Authentication composition |
| --- | ---: | --- |
| large-desktop | 1440×900 | split brand/form |
| laptop | 1280×800 | primary compact split target |
| compact-laptop | 1024×768 | lower-bound split target |
| tablet | 768×1024 | form-first; brand panel removed from layout |
| mobile | 390×844 | single-column form; SSO actions stacked |
| small-mobile | 360×800 | smallest canonical form-first target |

Responsive ownership rules:

- smaller viewports recompose rather than shrink the split desktop surface;
- the brand panel is present only at `lg+`; below `lg`, the form panel owns the visible KAORI identity;
- form content stays bounded by the existing `max-w-md` reading width while the outer panel remains viewport-safe;
- primary credential controls and browser SSO actions retain the 44 px interaction-height contract;
- one SSO provider is full width; multiple providers stack below `sm` and use a two-column grid from `sm+`;
- page-level horizontal scrolling is prohibited;
- phone layouts may grow vertically and use normal document scrolling rather than clipping authentication actions to preserve desktop card height;
- light/dark mode, focus visibility, accessible names, and authentication semantics remain equivalent at every canonical viewport.

Real-device UAT may add evidence, but physical device names do not become CSS contracts.

### Canonical Database Setup Workspace Composition

The approved Database Setup Required surface is a non-Hero, console-first readiness workspace optimized for the canonical 1280×800 and 1024×768 laptop targets. The setup surface intentionally does **not** use the authenticated application page-title scale because this is a short, one-time pre-authentication operator workflow.

Compact setup typography:

- page title: 18 px (`text-lg`), semibold;
- operator section title: 14 px (`text-sm`), semibold;
- explanatory and helper copy: 12 px (`text-xs`) with 20 px line height;
- technical command text remains 12 px monospace;
- semantic state labels remain owned by the shared label component.

This exception is limited to Database Setup Required and must not be copied to ordinary authenticated application pages.

The setup page uses **no giant outer workspace card and no permanent right-side setup rail**. The page is composed as a short operator console:

```text
Compact Page Identity
↓
Readiness Strip: Database | Application Schema | Normal Sign-In
↓
Bootstrap Console (2/3) | Encryption Boundary (1/3)
↓
Horizontal Initialization Path
↓
Advanced Setup (collapsed by default)
↓
Read-only Boundary + Retry Setup Check
```

The primary path must fit within the first laptop viewport under normal browser zoom whenever ordinary browser chrome allows it. Secondary manual recovery commands and missing-schema evidence stay behind the shared expandable-content component so they do not permanently inflate the page.

Shared ownership is mandatory:

- `components/table_label.html` owns installation, PostgreSQL, schema, and sign-in semantic labels;
- `components/terminal_command.html` owns copyable bootstrap/check commands and uses `compact=true` on this setup surface;
- `components/operational_callout.html` owns the encryption and connectivity semantic boundaries;
- `components/operational_flow_steps.html` owns the visible three-stage initialization sequence;
- `components/view_more_content.html` owns the collapsed Advanced Setup disclosure;
- `components/section_link_button.html` owns Retry Setup Check.

The setup page must not introduce authenticated Hero geometry, a giant parent card, a permanent troubleshooting rail, a vertical timeline that consumes most of the viewport, duplicate readiness summaries, page-local terminal chrome, arbitrary typography, custom CSS, provider calls, or database mutation from presentation code.

## Locked Security Contract

- Login is rate-limited and Flask-WTF owns CSRF validation.
- Credential failures remain provider/role neutral to avoid account-state disclosure.
- Post-login and SSO callback redirects accept only same-origin absolute paths.
- Successful authentication rotates session state before retaining authentication ownership.
- Logout is POST-only, authenticated, and preserves remember-cookie revocation.
- Remember Me defaults to 7 days, is bounded to 1–30 days, and remains default-deny for `super_admin` unless explicitly enabled.
- Production session and remember cookies remain Secure, HttpOnly, and SameSite=Lax.
- SSO state is fingerprinted, nonce is used when required, and the browser flow is TTL bounded.
- Failed authentication may identify a target account for evidence but never claims that target as the authenticated actor.

## Release Evidence

| Layer | Evidence |
| --- | --- |
| Static Quality | `verify_authentication_surface_final_lock.py`, Ruff, djLint, Pyright, UI debt guards, JS syntax |
| Contract | `tests/contracts/auth/` |
| Unit | `tests/unit/auth/test_auth_session_policy.py` |
| Functional | `tests/access/authentication/test_login_characterization.py` |
| Security Regression | `tests/security/auth/test_authentication_security.py` |
| Rendering/UI | `tests/rendering/auth/test_authentication_rendering.py` |
| E2E Smoke | `tests/e2e/auth/test_authentication_smoke.py` |
| Integration | **N/A** — this presentation lock adds no provider, persistence, LDAP, OAuth/OIDC, or external-runtime integration boundary |

Future Authentication Surface work requires a concrete defect, security requirement, or approved product change. Cosmetic redesign alone does not reopen this baseline.
