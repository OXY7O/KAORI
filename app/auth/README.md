# Authentication domain

Authentication owns login flows, provider handling, login audit recording, and security-result presentation.

## Boundaries

- `services.py`: authentication use cases.
- `providers/`: provider-specific adapters.
- `audit.py`: login success/failure audit persistence.
- `results.py`: typed authentication outcomes.
- `routes.py`: request/session boundary.

Login Activity is separate from Operational Activity. Never copy credentials, tokens, provider payloads, or raw authentication exceptions into user-visible audit records. Provider adapters return normalized results to the service layer.

## Login presentation contract

- The login page describes KAORI through global infrastructure-operation capabilities, not through the technologies or products currently integrated.
- Capability messaging may cover visibility, controlled operations, operational intelligence, governance, reporting, audit, and administration.
- The login page must not claim that a capability or integration is available to the user before authentication and RBAC evaluation.
- After successful authentication, the user is redirected to the role-aware Welcome workspace catalog.
- Login presentation is maintained in `templates/auth/` and `static/css/auth-login.css`; authentication behavior remains owned by the Python service and route layers.
