# RBAC domain

RBAC defines KAORI permissions, protected default roles, access checks, and role
management rules.

## Rules

- `defaults.py` is the canonical default-role and permission seed definition.
- `decorators.py` enforces route-level permission checks.
- `service.py` owns role and permission business rules.

Protected default roles cannot be edited like custom roles. A user cannot delete or
deactivate themselves. Admins cannot manage peer admins, and the last super admin
must remain available. UI visibility is not authorization; every protected action
must enforce permissions server-side.
