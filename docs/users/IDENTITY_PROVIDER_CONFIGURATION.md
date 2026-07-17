# Identity Provider Configuration

## Ownership

Identity provider configuration belongs to the standalone `app/users` domain because it supports identity discovery, projection, lifecycle administration, and synchronization. Authentication adapters consume the configuration but do not own user administration.

SQLAlchemy models remain centralized in `app/models/identity.py`.

## LDAP fields

- Provider key and display name
- Enabled state
- LDAP server URI
- Base DN
- Bind DN
- Bind-password environment-variable name
- User search filter
- TLS mode: LDAPS, StartTLS, or development-only plain LDAP
- Username, email, display-name, and stable-ID attributes
- Connection timeout

The database stores only the environment-variable name for the bind password. The secret value stays in runtime secret management.

## Stable identity

LDAP projection uses:

```text
provider_id + stable directory object identifier
```

Username, email, and display name are mutable attributes and must not be used as immutable identity keys.

## Search and provisioning

The administrator searches one enabled LDAP provider using a minimum two-character query. Results are capped. Selecting a result creates:

- one `User` record with `auth_source=ldap`;
- one `ExternalIdentityLink` record;
- no local password hash;
- one Activity Audit event.

A duplicate provider/subject link, username, or email is rejected.

## Security baseline

- Production must use LDAPS or StartTLS.
- JIT is disabled until role mapping is implemented.
- LDAP bind secrets are not stored in database configuration.
- External users cannot be promoted to break-glass super admin through directory provisioning.
- Local Database remains available independently of LDAP health.
