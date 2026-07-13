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
