# Analytics Alerts Alertmanager Exception Normalization

## Status

Implemented in Batch 3, Slice 4.

This slice closes the provider-failure asymmetry recorded by the source fallback
characterization. Unexpected Alertmanager exceptions no longer escape the
Analytics Alerts source boundary.

## Behavioral Contract

`load_alertmanager_alerts()` now converts unexpected provider exceptions into a
canonical `AlertSourceStatus`:

```text
source=alertmanager
selected_source=alertmanager
resolved_source=none
label=Alertmanager Error
configured=true
connected=false
fallback_used=false
fallback_reason=null
error=<original exception message>
```

The original exception is also recorded with `logger.exception()` and includes
the affected cluster identifier. This preserves stack-trace evidence for
operational diagnosis without exposing an uncaught exception to page, dashboard,
or report consumers.

## Automatic Source Behavior

When source selection is `auto`:

1. KAORI attempts Alertmanager.
2. An unexpected Alertmanager exception becomes a disconnected source status.
3. KAORI attempts the Prometheus `ALERTS` fallback.
4. If Prometheus connects, the returned status retains the original
   Alertmanager error in `fallback_reason`.
5. If Prometheus also fails, the combined source status retains both provider
   diagnostics.

Example fallback reason:

```text
Alertmanager unavailable: unexpected alertmanager failure. Using Prometheus ALERTS fallback.
```

## Explicit Source Isolation

Selecting `alertmanager` explicitly does not call Prometheus. The exception is
normalized into an Alertmanager error status and returned directly. This keeps
explicit-source behavior deterministic and prevents hidden cross-provider
substitution.

## Non-Goals

This slice does not change:

- alert payload normalization;
- severity or status semantics;
- routing, silence, or inhibition behavior;
- ownership and runbook resolution;
- readiness scoring;
- Prometheus exception handling;
- UI dictionary shapes.

## Verification

Behavior is protected by controlled-fake coverage in:

```text
tests/analytics/test_alerts_source_fallback_characterization.py
```

The release gate invokes that file explicitly through
`scripts/quality_gate.sh`.
