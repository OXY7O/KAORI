# KAORI Health Interpretation Standard

## Purpose

The Health Interpretation component translates one provider runtime score into an operator-readable health posture. It must explain the current score, the semantic range, the evidence that contributed to the score, and the boundary between runtime health and validation readiness.

Use it inside a provider runtime workspace after the compact runtime metrics and before detailed diagnostics.

## Information architecture

The component contains two coordinated areas:

1. **Current Health Posture**
   - current health score;
   - semantic health status;
   - one concise interpretation sentence;
   - readiness boundary;
   - three fixed score ranges.
2. **Contributing Evidence**
   - one row per weighted factor;
   - related semantic icon;
   - factor label and concise evidence;
   - factor score as a semantic status label.

Do not separate the score, thresholds, and contributing evidence into unrelated cards. They are one interpretation contract.

## Visual contract

- one clean bordered container with a restrained shadow;
- compact header with icon, Title Case title, sentence-case description, and current semantic status;
- five-column desktop grid: two columns for current posture and three columns for contributing evidence;
- stacked layout on smaller screens;
- semantic status colors only where health meaning exists;
- Violet is reserved for the readiness boundary and KAORI contextual guidance;
- no decorative chart background, oversized gauge, or empty vertical space.

The current posture may use Normal, Warning, Critical, or Unknown semantic treatment. The contributing-evidence rows use the same score thresholds as the provider health contract.

## Score contract

The standard health ranges are:

```text
0–59    Critical
60–84   Attention
85–100  Healthy
```

The currently active range may include the word `Current`. Unknown or not-observed posture must not be presented as Critical solely because the numeric placeholder is zero.

## Runtime and readiness boundary

Runtime health and validation readiness are related but separate:

- **Runtime health** describes the latest operational observation.
- **Readiness** describes whether saved configuration and validated capabilities satisfy the required contract.

The component must show this boundary directly. A healthy observation does not replace Full Validation, and a ready source can still become operationally unhealthy.

## Content rules

- Title: `Health Interpretation`.
- Description: one concise sentence explaining that the panel maps runtime evidence to health posture.
- Summary: one operator-readable sentence from the latest runtime state.
- Factor labels: Title Case.
- Factor details: sentence case and concise.
- Do not add remediation steps here; remediation belongs in Diagnostic Pipeline or capability validation.
- Do not add actions inside the component.

## Accessibility

- The component uses a labelled section.
- Semantic posture is communicated with text and icon, not color alone.
- Score ranges are visible as text.
- The component must remain understandable without a chart.
- Evidence rows remain in document order on all breakpoints.

## Shared implementation

```jinja
{% import "components/health_interpretation.html" as health_interpretation %}

{{ health_interpretation.render(
    runtime_state.health_score,
    runtime_state.health_status_label,
    health_tone,
    health_icon,
    runtime_state.health_summary,
    runtime_state.factors,
    readiness_label=runtime_state.readiness_label
) }}
```

Do not copy the score-range or evidence-row markup into provider-local templates.

## Reference implementation

Alertmanager Instance Manage → Runtime & History → Health Interpretation is the reference implementation.

## Prohibited patterns

- oversized radial or donut score chart;
- score shown without textual posture;
- threshold legend disconnected from the current score;
- evidence truncated to the point that the operator cannot interpret it;
- readiness and health presented as the same state;
- actions or remediation lists embedded inside Health Interpretation;
- provider-specific colors that bypass KAORI semantic tokens.

## Review checklist

- Current score and semantic posture are visible together.
- Readiness boundary is explicit.
- All three score ranges are visible.
- Unknown posture is not mislabeled Critical.
- Contributing factors include icon, label, evidence, and score.
- No decorative radial chart remains.
- Detailed remediation stays in Diagnostic Pipeline or Validation.

Prometheus Instance Manage and cluster-bound Prometheus Configuration are additional reference implementations. They must import the same shared component and must not maintain provider-local score ranges, gauges, or evidence-row geometry.

Alertmanager and Prometheus Manage are reference implementations inside the shared Integration Manage Workspace.
