# KAORI Naming Conventions

## Purpose

KAORI uses one canonical vocabulary across UI, reports, exports, notifications, audit evidence, APIs, and provider integrations. New modules must reuse these names instead of introducing local abbreviations.

## Environment names

User-facing environment names must always be written in full. Compact labels may reduce padding or font size, but must not abbreviate the value.

| Canonical value | Display name | Accepted legacy input aliases |
|---|---|---|
| `development` | Development | `dev` |
| `staging` | Staging | `stg`, `stage` |
| `production` | Production | `prd`, `prod` |
| `quality_assurance` | Quality Assurance | `qa` |
| `user_acceptance_testing` | User Acceptance Testing | `uat` |
| `testing` | Testing | `test` |
| `pre_production` | Pre-Production | `preprod`, `pre-prod` |
| `non_production` | Non-Production | `np`, `nonprod`, `non-prod` |
| `disaster_recovery` | Disaster Recovery | `dr`, `drc` |
| `laboratory` | Laboratory | `lab` |
| `proof_of_concept` | Proof of Concept | `poc` |
| `demonstration` | Demonstration | `demo` |
| `sandbox` | Sandbox | none |

### Enforcement

- Prefer canonical values for new integration foundations, but do not change existing stored cluster values without a dedicated migration.
- Continue accepting legacy aliases at input and filter boundaries.
- Render all values through `get_environment_label()` or the Jinja `environment_name` filter.
- Never use `title`, `upper`, or local template conditionals to format an environment.
- Environment is descriptive metadata and uses the KAORI violet metadata label, not an operational status color.
- Raw stored values may remain unchanged until a dedicated data migration is approved.

## General UI names

Use complete terms in headings, labels, buttons, tables, notifications, and audit descriptions:

- Configuration, not Config.
- Compatibility, not Compat.
- Capabilities, not Cap.
- Diagnostics, not Diag.
- Authentication, not Auth, except protocol/product names such as OAuth.
- Connection, not Conn.
- Response, not Resp.

Official technology names and established technical identifiers are exempt, including ConfigMap, API, CPU, TLS, SSO, LDAP, RBAC, URL, HTTP, UUID, and PromQL.

## Ownership

`app/cluster/constants.py` owns environment canonicalization and display names until the shared integration foundation introduces a broader scope registry. Provider modules and templates must not maintain separate environment maps.
