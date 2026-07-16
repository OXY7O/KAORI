# Prometheus integration

Prometheus is managed under the top-level **Integrations** domain and remains bound one-to-one to a Kubernetes cluster for the current Kubernetes architecture. The generic binding model must still allow a future centralized Prometheus instance for Server assets.

The driver detects the version from `/api/v1/status/buildinfo`, validates an instant query, and matches `prometheus-http-api-v1`. Configuration changes invalidate prior validation.

Do not add unversioned PromQL directly to routes or templates. Queries remain centralized in `queries.py`; the next query-registry increment must add metadata for required metrics, labels, expected result type, deprecation, and replacement profile.

Prometheus `0.39.2` is intentionally unsupported by the initial profile. Do not bypass the block without proving API and query compatibility and adding tests.
