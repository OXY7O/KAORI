# Analytics Alerts Source Failure and Fallback Characterization

## Status

Implemented in Batch 3, Slice 3.

This slice freezes the current Analytics Alerts source-resolution behavior with
controlled fakes. It does not change alert scoring, routing, silence matching,
inhibition, ownership, readiness, or output dictionary shapes.

## Characterized Source Matrix

| Selected source | Alertmanager | Prometheus | Current result |
| --- | --- | --- | --- |
| `auto` | connected | not called | Alertmanager result; no fallback |
| `auto` | unavailable | connected | Prometheus result with explicit fallback reason |
| `auto` | unavailable | unavailable | empty result with combined source diagnostics |
| `alertmanager` | unavailable | not called | Alertmanager failure returned directly |
| `prometheus` | not called | unavailable | Prometheus failure returned directly |

Explicit provider selection never crosses to another provider. Automatic source
selection prefers Alertmanager and only calls Prometheus after Alertmanager
reports that it is not connected.

## Malformed Payload Boundary

The current source adapters preserve these behaviors:

- Alertmanager ignores non-mapping entries inside an otherwise valid `alerts` list;
- Prometheus treats a non-list `data.result` value as an empty connected result;
- valid mapping entries continue through the canonical `NormalizedAlert` normalizers.

These are characterization statements, not recommendations. A future payload
validation hardening slice may deliberately change them with corresponding
contract and UI-message updates.

## Exception Boundary

Prometheus provider exceptions derived from `PrometheusError` are normalized to
an unavailable `AlertSourceStatus`. Unexpected generic Prometheus exceptions are
also converted to a disconnected error status by the existing loader.

Unexpected Alertmanager exceptions currently remain visible to the caller. This
asymmetry is intentionally recorded rather than silently changed in the same
commit as characterization coverage. Normalizing that boundary requires a
dedicated behavioral change because it affects automatic fallback and the error
shown to Analytics consumers.

## Release Gate

The source behavior is covered by:

```text
tests/analytics/test_alerts_source_fallback_characterization.py
```

The test is invoked explicitly by `scripts/quality_gate.sh` so environment-level
marker settings cannot silently deselect it.

## Next Decision

The next slice should decide and implement one consistent provider-failure
policy:

1. normalize unexpected Alertmanager exceptions and continue to Prometheus in
   `auto` mode; or
2. retain propagation and expose a dedicated dependency blocker.

The recommended direction is option 1 for availability, with the original
Alertmanager failure retained in `fallback_reason` and operational diagnostics.
