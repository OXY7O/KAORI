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

The approved Database Setup Required surface is a non-Hero, command-first readiness page optimized for the canonical 1280×800 and 1024×768 laptop targets. The setup surface intentionally does **not** use the authenticated application page-title scale because this is a short, one-time pre-authentication operator workflow.

Compact setup typography:

- page title: 18 px (`text-lg`), semibold;
- operator section title: 14 px (`text-sm`), semibold;
- explanatory and helper copy: 12 px (`text-xs`) with 20 px line height;
- technical command text remains 12 px monospace;
- semantic state labels remain owned by the shared label component.

This exception is limited to Database Setup Required and must not be copied to ordinary authenticated application pages.

**Current operator-feedback authority (#744, 2026-10-12): full
command-first redesign.** The earlier 2:1 card grid and later giant
nested outer frame are explicitly **REJECTED** by human review. Do not
reintroduce either layout. The operational page should explain one next
action clearly instead of assigning equal visual weight to many panels.

**100% zoom refinement (#744, operator screenshot review):** retain the
command-first composition, but present all sections on **one quiet,
light `bg-surface-card` workspace canvas** with `border-outline-subtle`
and `shadow-sm`. The workspace uses `max-w-6xl`, responsive
horizontal padding, and light/dark surface tokens so the content is
visibly distinct from `bg-surface-page` at normal browser zoom.
This is a **neutral white content surface**, not the previously rejected
thick Violet outer frame or nested multi-card dashboard.
The title/status, step rail and footer remain **unboxed within that
canvas**; the one bootstrap action keeps visual priority.
The key-flow instruction is **"Keep INTEGRATION_CREDENTIAL_KEY
unchanged."** and the hero description is **"PostgreSQL is ready. Run
setup to enable sign-in and background jobs."** The encryption
preflight callout continues to state verification before bootstrap.

**Approved composition for local Visual UAT:**

1. **Unboxed identity header:** KAORI initialization context, one main
   heading, short readiness explanation and semantic status badge.
   No Hero banner, giant parent container, or decorative card.
2. **Inline readiness rail:** one unboxed, border-separated definition
   list for Database / Application Schema / Normal Sign-In. Semantic
   values remain owned by `table_label`.
3. **One primary action panel:** the only dominant elevated surface.
   Full-width command-first bootstrap action with a Violet left
   boundary, concise guidance, terminal clipboard widget and
   operator-controlled execution notice. No sidebar rail or
   equal-height warning column.
4. **Preflight boundary:** a short, full-width semantic encryption
   callout *after* the main action, clearly instructing the operator to
   check the key before executing the copied command. It must never
   claim to generate or rotate credentials.
5. **Unboxed step rail:** use
   `operational_flow_steps.render(..., variant='inline')`. The new
   shared variant has no individual step cards, while the component's
   default `boxed` mode remains unchanged for all other pages.
6. **Secondary controls:** existing collapsed Advanced Setup and a
   subdued, unboxed read-only / Retry Setup Check footer.

Keep light/dark semantics, accessible labels, responsive stacking,
single `h1`, compact terminal ownership, copy behavior and fail-closed
PostgreSQL-unavailable state. The non-DevContainer/server guidance
must remain separate and must not receive the development migration
password. The setup screen remains **read-only**; it never performs
schema DDL or admin seed from the browser.

```text
KAORI Initialization · Database Setup Required            [state]
Connected DB / Schema Not Installed / Sign-In Unavailable
-----------------------------------------------------------
             ONE PRIMARY BOOTSTRAP ACTION
             [Copyable shared terminal command]
-----------------------------------------------------------
Encryption key preflight (semantic callout)
Inline step rail (no step cards)
Advanced Setup (collapsed)
Read-only note                                     [Retry]
```

No nested Violet frame, three-card status strip, boxed three-step
timeline, right-side warning rail, new page-local JS/CSS, or
duplicated provider calls. Previous screenshot variants were
superseded specifically by user feedback.
The primary path must fit within the first laptop viewport under normal browser zoom whenever ordinary browser chrome allows it. Secondary manual recovery commands and missing-schema evidence stay behind the shared expandable-content component so they do not permanently inflate the page.

Shared ownership is mandatory:

- `components/table_label.html` owns installation, PostgreSQL, schema, and sign-in semantic labels;
- `components/terminal_command.html` owns copyable bootstrap/check commands and uses `compact=true` on this setup surface;
- `components/operational_callout.html` owns the encryption and connectivity semantic boundaries;
- `components/operational_flow_steps.html` owns the visible three-stage initialization sequence;
- `components/view_more_content.html` owns the collapsed Advanced Setup disclosure;
- `components/section_link_button.html` owns Retry Setup Check.

The setup page must not introduce authenticated Hero geometry, an oversized/nested workspace frame, a permanent troubleshooting rail, boxed peer cards for the primary action path, duplicate readiness summaries, page-local terminal chrome, arbitrary typography, custom CSS, provider calls, or database mutation from presentation code.

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
