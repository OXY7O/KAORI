# Analytics Capability

`app/analytics/` is the capability boundary for KAORI analytics. Domain code is
owned by explicit asset packages; the capability root must not become a mixed
collection of Kubernetes, Object Storage, or provider-specific implementation.

## Canonical package layout

```text
app/analytics/
├── routes.py                  # category route composition only
├── shared/                    # domain- and provider-neutral contracts/helpers
│   ├── coercion.py
│   ├── params.py
│   └── metrics/
│       └── contracts.py       # canonical operational metric-source contract
├── kubernetes/                # complete Kubernetes Analytics domain
└── object_storage/            # complete Object Storage Analytics domain
    └── sources/               # provider adapters for canonical metric semantics
```

## Ownership rules

- Domain implementation belongs under an explicit asset namespace.
- `shared/` accepts code only when both its semantics and dependencies are
  genuinely domain-neutral. It is not a compatibility location.
- Provider query languages, clients, response parsing, credentials, and
  provider exceptions must not leak into domain services.
- Domain services consume canonical evidence contracts. Provider adapters own
  translation from those contracts to PromQL, CloudWatch, OpenTelemetry, or a
  future source implementation.
- Public route/blueprint contracts may remain stable when useful, but Python
  module ownership must use the canonical package directly. Do not add legacy
  import packages, aliases, forwarding modules, or compatibility wrappers.

## Current domains

### Kubernetes

`app.analytics.kubernetes` owns Kubernetes-specific analytics, committed
`AnalyticsSnapshot` materialization, worker orchestration, Kubernetes identity,
and Kubernetes/Metrics Source/Alertmanager interpretation. Its web request path is
worker-first and reads committed generations.

### Object Storage

`app.analytics.object_storage` owns provider-neutral Object Storage analytics.
Committed Object Storage Inventory supplies current-state evidence. Operational
time-series evidence is obtained through `MetricsSource`, resolved from the
asset's integration bindings. Concrete Metrics Source products are resolved through the integration adapter registry and are not the analytics
contract.

Interactive Object Storage queries are fail-fast: provider retry is disabled for
the request path, and a transport/authentication failure opens a request-local
source circuit so remaining metric reads are skipped. Query-specific failures
remain isolated so unrelated metrics can still render.

Alertmanager is optional for the current Object Storage baseline and must not be
required for metric-derived operational evidence.

## Architecture invariant

```text
Asset domain
    ↓
Canonical analytics semantics
    ↓
MetricsSource contract
    ↓
Domain source resolver
    ↓
Provider adapter
    ↓
Integration/provider runtime
```

Metric meaning belongs to KAORI; provider query syntax belongs to the adapter.
