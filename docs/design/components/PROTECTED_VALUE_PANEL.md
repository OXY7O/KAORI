# Protected Value Panel

## Purpose

`components/protected_value_panel.html` displays one approved, one-time sensitive value for a short server-defined window.

## Contract

The panel owns:

- sensitive-value identity and key name;
- encoding evidence;
- countdown;
- raw-value surface;
- automatic removal from the page;
- a safe cleared state.

The client controller is `app/static/js/secret_reveal_value.js`.

## Security rules

- No default Copy action.
- No HTMX history entry containing the value.
- No value in notifications, hero context, or Activity Audit metadata.
- Clear the value when the timer expires, the page becomes hidden, navigation begins, or its HTMX owner is replaced.
- Do not announce the countdown every second; update the accessible countdown at bounded intervals.
- The component does not weaken server-side one-time consumption, approval, step-up, or policy checks.
