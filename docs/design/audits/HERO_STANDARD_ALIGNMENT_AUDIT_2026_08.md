# Hero Standard Alignment Audit — August 2026

## Scope

This audit compared the active shared Hero implementation, global design documentation, Analytics domain documentation, contract tests, and quality-gate registration.

Canonical implementation:

```text
app/templates/components/page_hero.html
```

Canonical contract:

```text
docs/design/components/HERO.md
```

## Findings

The previous documentation estate had material drift:

- the active description used `text-base leading-7` while the document still stated 13 px / 20 px;
- context metric labels, values, and helpers were documented at scales different from the shared macro;
- global density rules alternated between two and four context metrics;
- two Analytics Hero documents repeated overlapping contracts;
- historical audits referenced test files that no longer existed;
- several contract tests still required removed posture-header and posture-notice APIs;
- seven unused Hero macros or action variants remained in the shared component;
- two public macro parameters were accepted but ignored;
- the UI style-debt baseline did not include accepted report-template changes already present in the source tree.

## Remediation

- Replaced `HERO.md` with v1.2, matching active Tailwind tokens and macro behavior.
- Added one domain extension: `components/ANALYTICS_HERO.md`.
- Removed the duplicate Analytics Hero documents.
- Marked July audit documents as historical snapshots and corrected active guardrail references.
- Removed unused macros:
  - `context_posture_header`;
  - `context_posture_note`;
  - `context_bottom_notice`;
  - `action_group_classes`;
  - `secondary_action_classes`;
  - `destructive_action_classes`;
  - `supporting_strip`.
- Removed ignored parameters from `context_metric_value_classes()` and `context_single_action_classes()`.
- Removed two obsolete duplicate Analytics Hero test files and consolidated their useful assertions into current contracts.
- Added `scripts/verify_hero_component_standard.py` and registered it in `scripts/quality_gate.sh`.
- Updated the UI style-debt baseline to reflect the accepted current tree.

## Active contract

The active Hero contract now locks:

- 248/280 px outer minimum height;
- 208/232 px internal grid minimum height;
- 20/24 px padding;
- 7/5 desktop layout;
- 30/36 px title;
- 16 px / 28 px-line-height description;
- 12 px metadata and context labels;
- 18 px context metric values;
- exactly two metrics in `context_card` and `context_card_body`;
- one full-width context action;
- stable Hero geometry during HTMX and background activity.

## Validation

- Hero standard verifier: passed.
- UI style-debt verifier: passed.
- Python syntax: passed across 799 files.
- Jinja parsing: passed across 532 templates.
- Focused Hero and related design contracts: 83 passed.
- Full contract suite baseline: 482 passed and 18 unrelated pre-existing failures remain outside this Hero/documentation scope.
