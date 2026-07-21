# Provider Persistence Authority

## Canonical Ownership

`IntegrationInstance` is the only database authority for shared provider fields:

- provider type;
- name and description;
- environment;
- enabled state;
- lifecycle status;
- readiness status;
- health status;
- last error;
- last checked timestamp.

`PrometheusInstance` and `AlertmanagerInstance` store only provider-specific
connection configuration and validation evidence.

## ORM Access

Provider records expose shared values through SQLAlchemy association proxies.
This is a domain-model composition mechanism, not a compatibility shim. No
duplicate provider columns are retained and no two-way synchronization is used.

Class-level filtering and ordering by provider name must join
`IntegrationInstance`; provider-specific tables do not own a `name` column.

## Development Reset

Revision `20260722_provider_authority` is destructive by design. KAORI is still
in development, therefore existing provider rows are not migrated. Reset the
development database, apply all migrations, bootstrap the administrator, then
register and validate providers again.
