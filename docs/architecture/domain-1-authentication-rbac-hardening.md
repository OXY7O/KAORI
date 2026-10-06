# Domain 1 — Authentication, Users, RBAC, and Break-Glass Hardening

## Scope

This change hardens KAORI's server-side authorization boundary for persisted role lifecycle and administrative user mutations.

## Corrected behavior

A persisted role assignment is authoritative. When the assigned role is inactive, `User.has_permission()` now denies access instead of falling through to the code-owned default permission map for a matching role slug. Super-admin break-glass authority remains explicit and unaffected.

User lifecycle policy functions now independently verify the required permission before evaluating self-management, administrator-level, deleted-account, and last-super-admin guardrails. Route decorators remain the first HTTP boundary; service checks provide defense in depth for future callers, jobs, and tests.

## Validation

Functional tests cover active and inactive persisted roles, super-admin bypass, and service-level rejection without the required permission. Architecture contracts remain separate under `tests/contracts/rbac`.

## Deployment

No database migration is required. Deploy the application code normally. Existing inactive role assignments immediately stop granting permissions after process restart.

## Rollback

Revert `app/models/user.py` and `app/access/users/service.py` together with their tests and this document. Rollback restores the previous fallback behavior and is therefore not recommended after inactive roles are used as an access-revocation control.

## Changed files

- `app/models/user.py`
- `app/access/users/service.py`
- `tests/users/test_authorization_guardrails.py`
- `tests/contracts/rbac/test_authorization_boundary_contract.py`
- `docs/architecture/domain-1-authentication-rbac-hardening.md`
