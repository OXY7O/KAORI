# KAORI Navbar and Application Shell Standard v1.0

This document owns the authenticated top-navbar interaction contract.

Canonical implementation:

```text
app/templates/components/navigation/navbar.html
app/templates/components/navigation/_notification_center.html
app/static/js/navbar.js
app/templates/layouts/app.html
```

Canonical enforcement:

```text
scripts/verify_application_shell_standard.py
scripts/verify_javascript_syntax.py
tests/contracts/design/test_application_shell_interaction_contract.py
```

## Scope

The global navbar owns:

- sidebar collapse/expand control;
- breadcrumb/current-page context;
- Quick Actions;
- Notification Deck;
- Account menu.

These are application-shell utilities. Domain pages must not create parallel implementations.

## Alpine ownership

Navbar state and notification refresh behavior are owned by the named Alpine component `kaoriNavbar` in `app/static/js/navbar.js`.

The template uses only:

```html
x-data="kaoriNavbar"
```

Do not place a multi-method JavaScript object literal directly in the `x-data` attribute. Complex inline Alpine programs are prohibited because HTML/Jinja formatting can remove statement boundaries and make the whole navbar fail to initialize.

`navbar.js` must load before `alpine.min.js` so the `alpine:init` listener can register the component before Alpine initializes the page.

## Exclusive menu state

Only one navbar utility surface is open at a time:

- opening Quick Actions closes Notification Deck and Account;
- opening Notification Deck closes Quick Actions and Account;
- opening Account closes Quick Actions and Notification Deck;
- Escape closes all three.

Quick Actions and Account are anchored dropdowns. Notification Deck is the canonical right-side overlay/drawer surface.

## Notification refresh

Notification Deck snapshot refresh:

- uses same-origin credentials;
- requests JSON only;
- has a five-second abort timeout;
- avoids overlapping requests;
- queues one follow-up refresh when a request is already running;
- updates active/unread badges and reprocesses HTMX content;
- reports connection problems through UI state rather than breaking shell interaction.

A refresh failure must not disable Quick Actions or Account.

## Accessibility

- icon-only controls require `aria-label`;
- expandable controls expose `aria-expanded`;
- Notification Deck exposes dialog semantics;
- Escape closes active shell surfaces;
- all interactive controls retain visible keyboard focus;
- decorative icons do not carry the accessible name.

## JavaScript quality gate

Every first-party file under `app/static/js/`, `frontend/**/*.js`, and `scripts/**/*.mjs` must parse with Node's syntax checker. Prettier remains the formatting authority. The shell verifier additionally rejects a complex inline navbar `x-data` implementation.
