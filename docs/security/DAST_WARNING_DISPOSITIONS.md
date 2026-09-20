# KAORI DAST Warning Dispositions

This document records reviewed dispositions for the warning families observed by the KAORI ZAP baseline. It is evidence for operator/security review; it does **not** replace the runtime DAST gate. The baseline remains authoritative for new failures, and `FAIL-NEW` must remain zero.

Current evidence source: KAORI staging Runtime & DAST, ZAP 2.17.0.

| Alert | Disposition | KAORI evidence / action |
| --- | --- | --- |
| 10031 — User Controllable HTML Element Attribute (Potential XSS) | Reviewed informational / narrow false-positive candidate | ZAP documents this as an informational passive finding requiring manual validation. `tests/security/test_http_response_security.py` injects an attribute-breaking `next` payload containing quotes, SVG/onload, autofocus and onfocus. The parser proves it remains only the hidden input value and creates no SVG or event attributes. Do not weaken or remove this proof. |
| 10049 — Non-Storable Content | Reviewed informational | ZAP classifies the cacheability family as informational. KAORI authentication/session-bearing and dynamic HTML is intentionally allowed to be non-storable. Do not make authentication responses cacheable only to silence this alert. |
| 10055 — CSP: script-src unsafe-eval | Temporary hardening debt | KAORI keeps `'unsafe-eval'` only because the standard Alpine runtime evaluates expressions dynamically. Inline script execution remains nonce-protected, `'unsafe-inline'` is not permitted for scripts, and `script-src-attr 'none'` blocks inline event-handler attributes. Migration target: the official `@alpinejs/csp` build, after all KAORI Alpine expressions are proven compatible and the package/lockfile is regenerated through the normal package-manager workflow. |
| 10109 — Modern Web Application | Informational discovery | ZAP identifies the application as modern/dynamic. Retain as scanner evidence; it is not a defect by itself. |
| 10111 — Authentication Request Identified | Informational authentication-helper evidence | ZAP has identified the login request. Retain as useful authentication-discovery evidence rather than suppressing it as a vulnerability. |
| 10112 — Session Management Response Identified | Informational authentication-helper evidence | ZAP has identified KAORI session handling from responses. Retain as useful discovery evidence. |
| 90004-2 — Cross-origin isolation headers | Hardened with staged evidence | KAORI's core browser assets are self-hosted and SSO uses top-level navigation rather than popup/iframe flows. CI #843 proved HTML COEP/COOP removed the prior COEP finding, then exposed CORP-missing on resource responses. `Cross-Origin-Resource-Policy: same-origin` is therefore applied to all responses, while `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` remain HTML/document-only. Runtime regression tests lock this boundary. |

## Centralized response-security contract

Browser response-security ownership remains in `app/bootstrap/security.py`. Page-local templates must not introduce their own competing CSP or site-isolation headers.

The HTML baseline is:

- nonce-protected `script-src 'self'`;
- temporary Alpine compatibility allowance `'unsafe-eval'`;
- no script `'unsafe-inline'`;
- `script-src-attr 'none'`;
- `frame-ancestors 'none'`;
- `object-src 'none'`;
- `Cross-Origin-Opener-Policy: same-origin`;
- `Cross-Origin-Embedder-Policy: require-corp`;
- `Cross-Origin-Resource-Policy: same-origin` on all responses.

Static/resource responses receive CORP plus MIME-sniffing protection, but do not receive document-level COEP/COOP headers.

## Scanner authority

Do not add broad ZAP ignore rules for these families. `.github/ci/run-zap-baseline.sh` remains the runtime scanner authority and the staging/release gate must continue to reject any genuine new failure. Reviewed warning dispositions are documentation and regression evidence, not permission to make `FAIL-NEW` non-zero.

## References

- ZAP 10031: https://www.zaproxy.org/docs/alerts/10031/
- ZAP 10049: https://www.zaproxy.org/docs/alerts/10049/
- ZAP 10055-10: https://www.zaproxy.org/docs/alerts/10055-10/
- ZAP 10109: https://www.zaproxy.org/docs/alerts/10109/
- ZAP 10111: https://www.zaproxy.org/docs/alerts/10111/
- ZAP 10112: https://www.zaproxy.org/docs/alerts/10112/
- ZAP 90004-2: https://www.zaproxy.org/docs/alerts/90004-2/
- Alpine CSP build: https://alpinejs.dev/advanced/csp
