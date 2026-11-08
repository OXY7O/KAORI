# Integration Operation and Route Boundaries

## Worker Contract

Integration workers dispatch provider operations through
`execute_integration_operation()`. Workers may load shared job and binding
records, but they must not import provider service functions directly.

Metrics Source and Alertmanager publish `binding.validate` through their registered
adapter modules. The operation is assigned to the `integration-validation`
queue and uses the same registry authority as runtime validation and health
refresh.

## Route Contract

`app/integrations/routes.py` owns HTTP concerns only:

- request parsing;
- permission checks;
- redirect or HTMX response selection;
- operational feedback presentation.

Provider record lookup and cross-provider binding creation are delegated to:

- `app/integrations/repository.py`;
- `app/integrations/binding_service.py`.

Routes must not query Kubernetes, Metrics Source, Alertmanager, or Cluster models
directly and must not import provider binding services.


## Notification Channel delivery journal recovery

Integrations → Notification Channels is the provider-neutral outbound transport
boundary. Producers (Reports, Alert Intelligence, etc.) remain authoritative for
event meaning, source identity and policy; the committed NotificationDelivery
journal owns transport execution state and replay eligibility.

The transaction boundary is **commit queued intent and encrypted immutable
transport snapshot → call external adapter → commit provider outcome**. Recovery
uses PostgreSQL `SKIP LOCKED` claims and bounded attempt/backoff policy,
revalidating channel policy plus original destination/credentials before replay.
External providers own delivery acceptance; a remote success before an interrupted
local commit can still be redelivered. The supported contract is at-least-once
attempts with journal deduplication after committed success, **not exactly-once
remote message delivery**. Legacy journal rows without replay snapshots are
not silently reconstructed.

The background Celery recovery schedule is **disabled by default** until
authorized UAT, enabled by `NOTIFICATION_DELIVERY_RECOVERY_ENABLED=true`.
It is independent of Alert Intelligence scheduling and uses the existing
maintenance worker queue. Details, safe bounds, key rotation, and UAT are
documented in `app/integrations/README.md`.
