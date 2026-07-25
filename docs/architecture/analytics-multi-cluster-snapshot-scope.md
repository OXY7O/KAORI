# Analytics Multi-Cluster Snapshot Scope

## Selection contract

Analytics pages must scope every request to one Kubernetes cluster. An explicit
`cluster_id` is authoritative even when that cluster has incomplete Prometheus
readiness, allowing KAORI to show a blocker for the selected cluster only.

When an analytics URL does not include `cluster_id`, KAORI prefers the first
registered cluster with an eligible Prometheus binding. If no cluster is
analytics-ready, KAORI falls back to the first registered cluster and presents
its setup/readiness blocker.

This prevents an unrelated unready cluster from becoming the implicit default
and blocking access to another ready cluster.

## Snapshot presentation contract

Committed analytics snapshots are read-only presentation payloads. Cluster
identities inside snapshot payloads are decoded into immutable scalar
references (`id`, `name`, `environment`, and `status`), never SQLAlchemy ORM
entities.

This boundary prevents background job dispatch commits or scoped-session
teardown from producing detached ORM objects during Jinja rendering. Existing
snapshots that only contain a cluster ID remain readable through a scalar-column
compatibility lookup.

## Operational behavior

- Explicit Cluster A selection + incomplete readiness: only Cluster A is blocked.
- Explicit Cluster B selection + ready Prometheus: Cluster B analytics remain available.
- No cluster in the URL: the first analytics-ready cluster is selected.
- Snapshot refresh dispatch cannot detach the cluster object used by the page.
