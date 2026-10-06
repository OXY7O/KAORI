# KAORI Workspace Summary Card Standard

## Purpose

The Workspace Summary Card presents one concise peer-level fact about the current tab or operational workspace. A row of these cards gives users a fast orientation before they enter the primary form, table, or diagnostic content.

Use the component immediately below a tab bar or page header when two to four summaries share the same information level.

## Visual contract

Every card in the same summary row uses the same KAORI Violet treatment:

- `rounded-xl`;
- Violet Soft surface;
- Violet outline;
- restrained shadow;
- 16 px internal padding;
- 36 px icon surface with a Violet outline and clean card surface;
- 14 px semibold Title Case title;
- 12 px sentence-case description with 20 px line height.

Do not make only one peer card Violet while rendering the others neutral. Visual emphasis must not imply hierarchy when all cards are equal summaries.

## Content contract

Each card contains:

1. one related icon;
2. one short Title Case title;
3. one concise sentence-case explanation.

Use two to four cards. Do not add actions, metrics, status badges, expandable content, long paragraphs, or nested lists.

If one item represents an actual warning, critical state, or current status, use the semantic status component instead of changing one Workspace Summary Card locally.

## Shared implementation

```jinja
{% import "components/workspace_summary_card.html" as workspace_summary_card %}

{{ workspace_summary_card.render(
    'Connection Contract',
    'Identity and access settings define how KAORI reaches this source.',
    icon='file-key-2'
) }}
```

Do not copy the card geometry into page-local templates.

## Reference implementation

Alertmanager Instance Manage provides the reference implementations across three tabs:

- Configuration: Connection Contract, Change Impact, Integration Flow;
- Validation: What Validation Does, Why It Matters, Operator Flow;
- Runtime: Readiness Versus Health, How Monitoring Works, Resolver Correlation.

Every row uses the same Violet surface because its cards are peer summaries.

## Review checklist

- Two to four peer summaries.
- Same component and surface for every card in the row.
- Related icon for each item.
- Title Case title and concise sentence-case description.
- No local hierarchy created through mixed card colors.
- No action, metric, status, list, or expandable content.

## Metrics Source reference rows

Metrics Source Instance Manage and cluster-bound Metrics Source Configuration use the same peer-level summary treatment:

```text
Configuration
├── Connection Contract
├── Change Impact
└── Integration Flow or Cluster Context

Validation
├── What Validation Does
├── Why It Matters
└── Operator Flow

Runtime
├── Readiness Versus Health
├── How Monitoring Works
└── Resolver Correlation or Consumer Boundary

Scope
├── Binding
├── Eligibility
└── Resolution
```

All cards in one row use the same Violet treatment. Lifecycle warnings and destructive actions remain separate semantic panels.

The Configuration, Validation, and Runtime tabs of Alertmanager and Metrics Source use identical three-card summary rows.
