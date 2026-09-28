# KAORI One-Time Secret Delivery

## Purpose

`components/one_time_secret.html` is the canonical KAORI surface for explicitly generated secret material that an authorized operator must copy or download once without turning routine inventory into a secret viewer.

Use this component only when the owning capability already authorizes material delivery. It does not create authorization by itself.

## Boundary

Routine registries, detail pages, Activity, reports, audit evidence, and operational summaries remain non-secret.

The one-time delivery flow is explicit:

1. an authorized operator opens the material request dialog;
2. the operator selects the governed target and bounded material lifetime;
3. the server generates new provider-backed material;
4. KAORI returns it in a non-cacheable one-time response;
5. the operator copies/downloads it;
6. KAORI retains only lifecycle/audit metadata, never the plaintext material.

A later request must mint new material rather than retrieve the previous value.

## Credential lifetime model

Credential **entitlement/review validity** and generated **secret-material lifetime** are separate contracts.

For Kubernetes Tenant credential delivery, current material policy is environment-aware:

- Development: maximum 24 hours;
- Staging: maximum 8 hours;
- Production: maximum 1 hour.

The UI may offer only choices admitted by the target environment. Server-side validation is authoritative and must enforce the same boundary when JavaScript is unavailable or bypassed.

Kubernetes remains authoritative for actual TokenRequest expiration. The one-time view must show the returned provider expiry and must not assume requested lifetime equals actual lifetime.

## Security response

The secret response must use:

- `Cache-Control: no-store, no-cache, must-revalidate, private`;
- `Pragma: no-cache`;
- `Expires: 0`;
- `Referrer-Policy: no-referrer`;
- `X-Robots-Tag: noindex, nofollow, noarchive`.

Secret material must not be written to application logs, Activity metadata, Notification payloads, database records, or routine HTML surfaces.

## Reusable UI

`request_dialog` provides the confirmation/lifetime request shell.

`material_block` provides a copy surface and optional client-side download. It reuses the global KAORI clipboard primitive and marks secret content with `data-kaori-sensitive-material` so owning page scripts can clear rendered material on page exit.

Do not create page-local secret-card/button styles when this component is sufficient.

## Kubernetes Tenant usage

- Human access: mint a short-lived ServiceAccount token for manual JumpServer credential delivery until direct JumpServer integration exists.
- CI/CD Deployer: mint a short-lived ServiceAccount token and construct a namespace-scoped kubeconfig; expose YAML and Base64 forms for bounded UAT/pipeline delivery.
- Do not create a legacy long-lived ServiceAccount Secret merely to match the longer credential entitlement period.

For recurring CI/CD that must work beyond a generated token lifetime, the target architecture should obtain fresh short-lived material at runtime (for example through an approved identity/broker integration) rather than extending one static bearer token to the entitlement lifetime.
