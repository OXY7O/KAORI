# Analytics Alerts Silence and Inhibition Contracts

## Purpose

This slice reduces the remaining broad presentation dictionaries in the KAORI
Alerts & Anomalies domain. It introduces focused typed contracts for
Alertmanager silence visibility and inhibition visibility while preserving the
existing runtime dictionary shapes consumed by templates, dashboards, reports,
readiness scoring, and recommendation logic.

This is a contract-only refactor. It does not redesign silence matching,
Alertmanager API behavior, inhibition detection, status wording, semantic
colors, or incident-readiness penalties.

## Canonical Contracts

The source of truth is `app/analytics/alerts/contracts.py`.

### Silence boundary

- `AlertSilenceApiStatus` describes whether the Alertmanager silence endpoint
  was reachable and preserves its error detail.
- `AlertSilenceMatcher` describes the normalized equality, negative, and regex
  matcher representation used by KAORI.
- `AlertSilenceItem` describes one active silence row prepared for presentation.
- `AlertSilenceSummary` describes the complete silence visibility block used by
  the application context and alert snapshot.

`AlertSilenceSummary` keeps the established runtime keys:

```text
enabled
level
label
description
class
icon
source
active_silences
pending_silences
expired_silences
matched_alerts
silenced_namespaces
silenced_matchers
items
```

### Inhibition boundary

- `AlertInhibitionItem` describes one inhibited-alert row.
- `AlertInhibitionSummary` describes the complete inhibition visibility block.

`AlertInhibitionSummary` keeps the established runtime keys:

```text
enabled
level
label
description
class
icon
source
rules_detected
matched_alerts
source_equal_labels
target_matchers
items
```

## Updated Ownership

`app/analytics/alerts/silences.py` owns:

- Alertmanager silence loading;
- Alertmanager datetime normalization;
- matcher normalization;
- equality, negative, and regex matcher evaluation;
- active, pending, and expired counts;
- matched-alert and namespace summaries;
- empty and unavailable silence states.

`app/analytics/alerts/inhibition.py` owns:

- inhibition visibility availability;
- inhibited-alert detection from `inhibited` and `inhibited_by` metadata;
- source-equal-label presentation;
- detected-rule counting;
- inhibited-alert presentation rows.

`AlertsSnapshot` now references `AlertSilenceSummary` and
`AlertInhibitionSummary` directly instead of `dict[str, Any]`.

## Behavior Preserved

The following behavior is intentionally unchanged:

- a silence without valid matchers does not match an alert;
- equality matchers require an exact value;
- negative matchers reject matching values;
- regex matchers use `re.search`;
- invalid regex patterns fall back to substring matching;
- only active silences are included in the presented item list;
- pending and expired silences remain count-only;
- Alertmanager must be the connected resolved source for full silence and
  inhibition visibility;
- Prometheus fallback remains `limited`, not `available`;
- inhibition rules are inferred from unique `inhibited_by` entries;
- only the first five silence and inhibition items are presented;
- incident-readiness scoring continues reading `matched_alerts` from both
  summaries.

All runtime values remain ordinary Python dictionaries and lists. No template,
report, or dashboard receives a class instance.

## Validation

The typed-contract tests verify:

- the focused contracts exist;
- the silence and inhibition builders use those contracts;
- `AlertsSnapshot` no longer uses broad dictionary annotations for these
  sections;
- empty runtime dictionaries have exactly the typed contract keys;
- the compatibility facade continues exporting the established contract names.

Characterization tests verify:

- empty silence and Prometheus-limited inhibition summaries retain their
  dictionary shapes;
- inhibition visibility still detects inhibited alerts, rule identifiers, and
  source-equal labels;
- existing silence matcher semantics remain unchanged.

A semantic AST comparison, with type annotations removed before comparison,
confirms that all eight silence functions and the inhibition builder preserve
their existing executable behavior.

## Next Slice

The next presentation-contract reduction should cover ownership and incident
readiness. It must not be combined with scoring changes, owner-precedence
changes, or new user-facing readiness wording.
