# Authentication domain

Authentication owns login flows, provider handling, login audit recording, and
security-result presentation.

## Boundaries

- `services.py`: authentication use cases.
- `providers/`: provider-specific adapters.
- `audit.py`: login success/failure audit persistence.
- `results.py`: typed authentication outcomes.
- `routes.py`: request/session boundary.

Login Activity is separate from Operational Activity. Never copy credentials,
tokens, provider payloads, or raw authentication exceptions into user-visible audit
records. Provider adapters return normalized results to the service layer.

## Login presentation direction

The login page introduces KAORI as a global infrastructure operations platform,
not as a list of currently integrated products. Keep the brand panel concise and
spacious:

- one short platform label;
- one two-line value statement;
- one supporting sentence;
- four compact capability cues: Visibility, Control, Intelligence, and Assurance.

Do not expand the login page into a feature catalog. Product-, provider-, and
asset-specific information belongs after authentication in role-aware workspaces.
The form description may explain that available workspaces follow the signed-in
user's role, while actual authorization must remain enforced on protected routes.

## Tailwind and design-system contract

The authentication presentation is the first reference implementation of the KAORI Violet Infrastructure design system. Its templates use Tailwind utilities and semantic tokens from `frontend/styles.css`; do not restore a page-specific authentication stylesheet or add raw hex colors to templates.

The current login action is the local database provider. Do not display actionable LDAP, SSO, password-recovery, or other provider controls until their routes and service contracts are implemented. Theme switching is available before authentication and uses the same `theme` local-storage key as the protected application shell.

Full visual rules: `docs/design/KAORI_DESIGN_SYSTEM.md`.
