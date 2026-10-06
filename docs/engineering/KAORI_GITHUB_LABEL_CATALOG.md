# KAORI GitHub Label Catalog

**Governance Version:** 1.0  
**Scope:** Repository metadata for Issues and Pull Requests  
**Lifecycle Authority:** GitHub Project `Status`  
**Type Authority:** Native GitHub Issue Type  
**Priority Authority:** GitHub Project `Priority`

KAORI labels describe domain ownership, implementation surface, quality concern, material impact, or an exceptional workflow condition. Labels do not replace native GitHub or Project metadata.

## Authority Rules

The repository uses one authority per concern:

- Lifecycle state → GitHub Project `Status`.
- Work classification → Native GitHub Issue Type.
- Priority → Project `Priority`.
- Estimate → Project `Story Points`.
- Sprint → Project `Sprint` iteration.
- Release target → GitHub Milestone.
- Documentation work → GitHub's built-in `documentation` label.
- Portable context → KAORI namespaced labels from this catalog.

Do not create custom labels that duplicate lifecycle, work type, priority, sprint, estimate, release target, or the retained built-in documentation label.

## Label Admission Gate

An uncataloged label must not be used. Before a new KAORI-owned label is created or applied, this catalog must define its **name, color, and description**, its namespace must be one of the canonical families, and its meaning must not overlap an existing native/Project authority or catalog entry.

Admission checks:

1. Confirm the label communicates portable context that is not already owned by Status, Native Issue Type, Priority, Story Points, Sprint, Milestone, ownership, or relationships.
2. Confirm the exact lowercase namespaced name is canonical and has no competing alias.
3. Record the deliberate color and concise applicability description in this catalog before repository use.
4. Use the smallest meaningful label set; do not add labels merely to make metadata look complete.
5. When connected tooling cannot administer the repository label definition, report the exact label name, color, description, and intended Issue/PR usage to the maintainer before applying it.

A label with no description, an uncataloged KAORI-owned label, or a label that duplicates native/Project metadata is non-canonical until it passes this gate.

## Naming Standard

KAORI-owned labels use lowercase namespaced names:

```text
<namespace>:<value>
```

Canonical namespaces:

- `area:*` — product or domain ownership.
- `scope:*` — implementation surface.
- `quality:*` — material quality attribute.
- `impact:*` — explicit delivery or release impact.
- `workflow:*` — exceptional workflow metadata only.

Use the smallest meaningful label set. A normal Issue should usually have one primary area label and only the additional scope, quality, impact, or workflow labels that materially apply.

## Area Labels

| Label | Color | Description |
| --- | --- | --- |
| `area:intelligence` | `9333EA` | Intelligence, Recommendations, Alert Intelligence, Rule Catalog, and governed automation. |
| `area:analytics` | `4F46E5` | Kubernetes and Object Storage analytics, capacity, forecasting, and anomaly analysis. |
| `area:reports` | `0891B2` | Report generation, publication, templates, schedules, artifacts, and storage. |
| `area:kubernetes` | `326CE5` | Kubernetes inventory, topology, governance, operations, and workflows. |
| `area:object-storage` | `0F766E` | Object Storage inventory, analytics, capacity, provider evidence, and request paths. |
| `area:integrations` | `0284C7` | Integration providers, registrations, bindings, compatibility, and readiness. |
| `area:settings` | `475569` | Settings, identity, authentication, users, roles, permissions, and accounts. |
| `area:platform` | `334155` | KAORI foundation, runtime, delivery, shared services, governance, and platform concerns. |
| `area:observability` | `0E7490` | Metrics, alerts, monitoring, telemetry, and operational evidence. |

## Scope Labels

| Label | Color | Description |
| --- | --- | --- |
| `scope:frontend` | `7C3AED` | Jinja, browser behavior, JavaScript, CSS, accessibility, and UI composition. |
| `scope:backend` | `2563EB` | Routes, services, workers, domain logic, adapters, and server-side behavior. |
| `scope:database` | `1D4ED8` | PostgreSQL, SQLAlchemy, persistence contracts, data changes, and Alembic migrations. |
| `scope:ci` | `0369A1` | CI/CD workflows, runners, build toolchains, tests, validation, and release automation. |

Documentation does not require a custom namespaced scope label. Use GitHub's built-in `documentation` label together with the appropriate `area:*` label.

## Quality Labels

| Label | Color | Description |
| --- | --- | --- |
| `quality:accessibility` | `6D28D9` | Accessibility, keyboard operation, semantics, or assistive-technology support. |
| `quality:security` | `BE123C` | Security controls, trust boundaries, authorization, vulnerabilities, or validation. |
| `quality:performance` | `0F766E` | Runtime, query, build, rendering, caching, or resource-efficiency performance. |
| `quality:ux` | `A855F7` | Human readability, interaction quality, hierarchy, or usability. |
| `quality:reliability` | `0E7490` | Correctness, resilience, deterministic behavior, recovery, or availability. |

## Impact Labels

| Label | Color | Description |
| --- | --- | --- |
| `impact:breaking` | `991B1B` | Breaking API, workflow, configuration, compatibility, or user-facing contract change. |
| `impact:migration` | `C2410C` | Schema/data migration, transformation, backfill, or compatibility migration. |
| `impact:security` | `BE123C` | Material security impact requiring explicit review and validation evidence. |
| `impact:data` | `B45309` | Material data ownership, integrity, retention, deletion, or lifecycle impact. |

## Workflow Exception Labels

| Label | Color | Description |
| --- | --- | --- |
| `workflow:blocked` | `111827` | Work cannot progress; blocker, owner, and unblock evidence must be recorded. |
| `workflow:expedite` | `E11D48` | Approved expedite/hotfix lane; normal quality, security, CI, and UAT gates remain required. |

`workflow:blocked` is exception metadata. The Issue remains at its meaningful Project lifecycle status instead of creating a second blocked lifecycle.

## GitHub Built-in Label Policy

| Built-in label | Decision | Handling |
| --- | --- | --- |
| `documentation` | Keep | Canonical documentation-work label. |
| `bug` | Retire from governed use | Native Issue Type **Bug** is authoritative. |
| `enhancement` | Retire from governed use | Use the appropriate native Issue Type. |
| `question` | Retire from governed use | Use the appropriate work type and record the question in the Issue. |
| `invalid` | Retire from governed use | Use Issue close reason and decision evidence. |
| `duplicate` | Keep | Collaboration metadata for a confirmed duplicate. |
| `good first issue` | Keep | Contributor-discovery metadata only. |
| `help wanted` | Keep | Contributor-assistance metadata only. |

Do not delete a still-referenced label before existing Issues or PRs are migrated to the canonical model.

## Legacy Alias Cleanup

Retire unnamespaced KAORI aliases after references are migrated:

- `ci` → `scope:ci`
- `reports` → `area:reports`
- generic `quality` → the specific applicable `quality:*` label

Do not create aliases with alternate spelling, capitalization, spaces, or hyphens.

## Labels Not Allowed

Do not create label families for concerns already owned elsewhere:

- work-type labels;
- priority labels;
- lifecycle/status labels;
- sprint or iteration labels;
- story-point or estimate labels;
- release-version labels;
- a custom documentation alias competing with GitHub's built-in `documentation` label.

## PR Metadata Rule

PR cards are integration evidence, not duplicate planning work items. Apply area/scope/quality/impact labels only when they help review or ownership. Do not invent planning labels to compensate for Project fields that GitHub does not expose on PR cards.

## Human-Readable Metadata Rule

Every KAORI-owned label must have:

- one canonical lowercase namespaced name;
- one deliberate color from this catalog;
- one concise description explaining when it applies;
- no competing alias.

The repository label list is a controlled vocabulary, not an accumulation of historical tags.

## Change Control

Changes to this catalog are governed repository changes. Migrate existing references before retiring a used label. When centralized Platform Governance becomes authoritative, converge this catalog through a versioned governance change and retain only KAORI-specific extensions that remain necessary.
