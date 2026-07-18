# Integration Consumer Pattern

A consumer is the only supported boundary between an asset domain and a provider integration.

## Simple consumer flow

```text
Analytics asks for data
        ↓
Consumer identifies the asset scope
        ↓
Resolver selects an eligible provider source
        ↓
Reader calls the selected provider
        ↓
Consumer returns canonical provider records
        ↓
Asset domain enriches and interprets the records
```

Analytics must not know the provider endpoint, credentials, TLS policy, compatibility profile, binding table, or HTTP client.

## Primary, secondary, and fallback in simple terms

These roles define preference, not simultaneous processing.

```text
Primary
→ first preferred source

Secondary
→ next source when it is healthier or the primary lacks a required capability

Fallback
→ last-resort source
```

Example:

```text
Cluster A requests alerts
        ↓
Primary supports Alerts API and is healthy
        ↓
Use Primary
```

If Primary is unhealthy:

```text
Cluster A requests alerts
        ↓
Primary is unhealthy
        ↓
Secondary is healthy
        ↓
Use Secondary
```

If the request is for silences and Primary lacks `silences_v2`:

```text
Cluster A requests silences
        ↓
Primary lacks Silences API
        ↓
Secondary has Silences API
        ↓
Use Secondary
```

The asset analytics code does not implement this selection.

## Resolver responsibilities

The resolver ranks bound sources using:

1. eligibility;
2. required capabilities;
3. runtime health;
4. readiness;
5. source role;
6. priority; and
7. deterministic tie-breaking.

It emits a decision trace explaining why each source was selected or skipped.

## Runtime fallback

Persisted state may become stale between validations. Therefore the consumer may try the next eligible source when the selected provider fails during the live request.

```text
Resolver selects Primary
        ↓
Live request fails
        ↓
Consumer tries Secondary
        ↓
Response records fallback_used and sanitized source errors
```

## Asset-domain boundary

Provider normalization remains generic. Kubernetes, Server, HCI, and Storage enrichment belongs to their own bounded contexts.

```text
Alertmanager consumer
→ canonical labels, annotations, state, timestamps, receiver, fingerprint

Kubernetes analytics
→ namespace, pod, workload, ownership, incident interpretation
```

## Required usage

New asset domains must consume providers through public consumer facades. Direct imports of provider models, repositories, credentials, clients, or validation services are prohibited outside the provider package and its approved compatibility layer.

## Canonical consumer result

All provider consumers should converge on the contracts in
`app/integrations/consumer/contracts.py`:

- `ConsumerSource` identifies the provider runtime selected for the operation;
- `ConsumerDiagnostic` carries safe operator guidance plus controlled technical detail;
- `ConsumerResult` carries the payload, capability requirements, source decision,
  diagnostics, and operation status.

Consumers own runtime-read gating. Provider validation services own configuration,
endpoint detection, compatibility mapping, capability discovery, and persistence.
Analytics owns interpretation of successful canonical data only.

Prometheus/Thanos uses a single consumer because Thanos Query is a
Prometheus-compatible query surface. The source metadata records whether the
actual endpoint product is Prometheus or Thanos, while capability evidence—not
backend version visibility—determines whether a query contract is available.

## Domain capability gates

A domain consumer may define a complete feature contract rather than allowing
individual queries to fail independently. Storage Analytics establishes the
initial implementation:

```text
Storage Analytics
  -> instant_query
  -> kubernetes_identity
  -> pvc_usage
  -> node_filesystem_identity
```

If any requirement is not satisfied, the domain is blocked before data queries
run. Connected-but-incomplete integrations must not be presented as feature
ready. Provider-specific identity workarounds, including treating
`instance="IP:port"` as a Kubernetes node name, are prohibited.


## Capacity Analytics contract

Capacity Analytics requires the complete consumer contract before it executes queries:

- `instant_query`
- `range_query`
- `kubernetes_identity`
- `capacity_metrics`
- `resource_requests_limits`

The contract covers worker allocatable CPU, memory and pods; current container usage; pod placement; node-role exclusion; and request/limit metrics. A connected endpoint is not sufficient. Missing metrics or incomplete canonical labels must block the feature and direct remediation to the Prometheus/Thanos source.

## Utilization capability contract

Utilization Analytics consumes Prometheus or Thanos only through `PrometheusConsumer` and requires instant query, range query, Kubernetes identity, utilization metrics, and canonical filesystem node identity. Node drill-down storage must use a canonical Kubernetes node label; `instance=IP:port` is not a supported identity fallback. Integration validation must report missing metrics or label remediation before the page is considered ready. Presentation strings introduced while touching Utilization templates are prepared in Python rather than formatted in Jinja.
