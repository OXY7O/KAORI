# KAORI Platform Operations Final Lock v1.5 Audit — 2026-08-08

## Review outcome

The review reproduced two cross-request inconsistencies and one minor pagination mismatch in Secret Reveal.

## Root causes

- Namespace-policy/readiness feedback was queued in the session even for HTMX partial responses. The main layout, which consumes the queue, is not rendered during the partial swap, so the toast appeared only on the next full page refresh.
- Protected Reveal built its namespace selector by listing every live Kubernetes namespace and intersecting that result with enabled policy records. Configuration enablement itself validates one namespace with `GET`, so the execution workspace required broader discovery privilege than the configuration boundary.
- The Namespace Policies footer had the page-size selector but omitted the visible `Rows` label.

## Corrected behavior

- HTMX mutations append the canonical operational toast OOB in the same response while still persisting Notification Deck / Activity Audit evidence.
- Normal redirect fallback continues to use queued operational feedback.
- Protected Reveal begins with policy-enabled namespace names and calls Namespace `GET` only for those configured targets. Missing namespaces are excluded; infrastructure/RBAC failures are shown explicitly.
- Protected Reveal explains why selectors are unavailable instead of collapsing all causes into a generic empty state.
- Namespace Policies now follows the canonical `Showing … Namespaces · Rows · page size` footer.

## Security result

The change reduces required discovery breadth without weakening authorization. Current cluster readiness, namespace policy, live Secret identity, approval requirements, step-up authentication, and final one-time reveal checks remain unchanged.
