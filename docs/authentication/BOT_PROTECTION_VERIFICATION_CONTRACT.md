# BP-01 — Bot Protection provider-neutral verification kernel

Authority: #3135 (BP-00), #3136 (BP-01), #638 Security, #641 identity boundary.

## Capability ownership

```text
Access → Authentication Security → Bot Protection
    → Protection Policy (disabled / adaptive / always, future BP-02)
    → Provider Registry (Cloudflare Turnstile first)
    → Provider Instance (site key, encrypted secret, hostname/action, future BP-02)
    → Server-side Siteverify adapter (BP-01 kernel)
    → Normalized verification result
    → Authentication admission (future BP-02)
```

External provider remains authoritative for one-time challenge verification. KAORI owns policy, safe normalizations, orchestration, committed audit and access governance. Bot Protection is **not** a primary Identity Provider, an integration clone or MFA.

## Current implementation status

`app/access/authentication/bot_protection/registry.py` registers only Cloudflare Turnstile with a pinned endpoint. `turnstile.py` implements **server-side standalone validation** and normalized results. It does NOT add login-route verification, admin config, persisted provider instances, frontend widgets, challenge policy activation, migration, remote calls on normal requests or new UI. No bot protection is enabled by this code alone. hCaptcha is a future provider and intentionally rejected by registry until adapter tests exist.

## Siteverify security rules

- Fixed `POST https://challenges.cloudflare.com/turnstile/v0/siteverify` (no dynamic URL), no redirects, HTTPS from system TLS validation, bounded connect/read timeout, stream/response cap and no remote IP submission by default.
- Require valid non-empty secret (never printed), token length 1–2048 ASCII (never logged), `success is true`, deployment-pinned hostname and login action, parseable offset-aware timestamp no more than 300s old and max 30s future tolerance.
- Normalize provider rejection, timeout, malformed reply and over-size response without copying raw vendor error, token or secret into KAORI audit/log output.
- Token redemption is provider-enforced **single use** (expires after 300 seconds). Reused tokens fail verification.
- Unit tests use injected HTTP transport; never depend on a live Turnstile account or external provider in CI.

Upstream contract (Cloudflare official): https://developers.cloudflare.com/turnstile/get-started/server-side-validation/

## Activation, outage and safety gates

BP-02 must register and protect actual provider instances using KAORI credential encryption and enforce challenge on login/SSO before credential/session issuance. A configured always/adaptive policy without a ready instance MUST fail closed; never silently fall back to disabled due to vendor outage. Preserve local break-glass with explicitly approved recovery path; never create a CAPTCHA bypass via unprotected admin form.

Do not claim end-to-end CAPTCHA protection, operator-configurable providers, readiness or UAT PASS from BP-01. Official CI and `kaori/staging` admission remain HOLD.

## BP-02 runtime extension (#3137)

Bot provider instance configuration lives in the committed `authentication_security_policies` row, with an encrypted verification secret. The initial supported activation policy is Disabled or Always. Cloudflare Siteverify enforcement gates credential authentication **before** password/provider evaluation and the start of SSO through a CSRF-bound POST; a legacy SSO GET is redirected when Always is active. Site key is public; secret never reaches the browser. The login-only CSP authorizes fixed Cloudflare resources and no dynamic external hosts.

Provider configuration presence is not independently verified connection readiness. Every required failure, timeout or malformed token rejects authentication. Out-of-band `flask disable-bot-protection` recovery requires privileged host access, incident reason and a committed audit. Adapter tests, real provider UAT, outage/recovery rehearsal and Human Acceptance are required before production policy activation. Adaptive behavior and hCaptcha remain future scoped work, not placeholders that can be enabled.
