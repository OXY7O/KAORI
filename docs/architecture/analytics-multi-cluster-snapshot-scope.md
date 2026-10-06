# Analytics Multi-Cluster Snapshot Scope

## Selection Contract

Analytics pages scope every request to one Kubernetes cluster. An explicit
`cluster_id` is authoritative even when that cluster has incomplete integration
readiness, allowing KAORI to show the blocker for the selected cluster only.

When an analytics URL does not include `cluster_id`, KAORI evaluates readiness
against the dataset being requested. Forecast, capacity, utilization, storage,
workload, and top-consumer pages prefer the first cluster whose bound Prometheus
source satisfies that dataset's binding and technical capability contract.
Alert datasets prefer a cluster with an eligible requested alert source.

If no cluster is eligible, KAORI falls back to the first registered cluster and
presents its scoped setup, connection, or capability blocker. An unrelated
unready Cluster A therefore cannot become the implicit blocker for ready
Cluster B.

## Materialized Request Contract

`MaterializedRequest` is the shared boundary between analytics routes and the
snapshot subsystem. It always exposes:

- the committed snapshot result;
- an immutable cluster reference;
- canonical snapshot parameters;
- dispatch state and dispatch error;
- an optional dependency blocker.

Routes may render a committed snapshot together with a current readiness
blocker, or render a full blocked state when no committed snapshot exists. A
blocked request must not dispatch another materialization job.

Snapshot parameters are canonicalized through the analytics dataset catalog.
View-only selectors such as forecast horizon, projection method, display
resource, search, pagination, and local filters must not create additional
snapshot fingerprints.

## Snapshot Presentation Contract

Committed analytics snapshots are read-only presentation payloads. Cluster
identities inside snapshot payloads decode into immutable scalar references
(`id`, `name`, `environment`, and `status`), never SQLAlchemy ORM entities.
This prevents background dispatch commits or scoped-session teardown from
causing `DetachedInstanceError` during Jinja rendering.

## Operational Behavior

- Explicit Cluster A + incomplete readiness: only Cluster A is blocked.
- Explicit Cluster B + ready source: Cluster B analytics remain available.
- No cluster in URL: KAORI selects the first dataset-ready cluster.
- No eligible cluster: KAORI shows the first cluster's scoped blocker.
- Dependency blocker present: no on-demand materialization is dispatched.
- Snapshot refresh dispatch cannot detach the cluster object used by the page.
