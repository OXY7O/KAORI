# Operational Toggle Audit — July 2026

## Scope

The audit reviewed boolean connection controls across Kubernetes, Prometheus, and Alertmanager integration forms and configuration workspaces.

## Findings

Equivalent controls used inconsistent surfaces:

- `Verify TLS Certificate` sometimes used violet emphasis;
- `Allow KAORI to Use This Connection` used a neutral surface;
- Kubernetes TLS controls used separate local markup;
- risk styling was not consistently tied to an actual exception.

## Standard Decision

Normal operational and security toggles use one neutral baseline. Semantic warning or critical color is used only when enabling a control creates a meaningful exception or risk.

## Implementation

A shared component was added:

```text
app/templates/components/operational_toggle.html
```

Applied to:

- Kubernetes cluster create and edit transport policy;
- Prometheus reusable connection create and edit;
- Prometheus cluster-bound configuration;
- Alertmanager reusable connection registration;
- Alertmanager cluster-bound configuration;
- Alertmanager instance configuration.

Standardized controls:

| Control | Tone | Reason |
|---|---|---|
| Verify Kubernetes API TLS Certificate | Neutral | Recommended baseline control. |
| Allow Legacy TLS Certificate | Warning | Explicitly weakens the current TLS policy. |
| Verify TLS Certificate | Neutral | Normal security control. |
| Allow KAORI to Use This Connection | Neutral | Normal lifecycle and resolver control. |

## Result

- Equal geometry for equivalent toggles: implemented.
- Neutral baseline across providers: implemented.
- Warning reserved for the legacy TLS exception: implemented.
- Local duplicate toggle containers removed from audited workspaces: implemented.
- Guardrail test: implemented.
