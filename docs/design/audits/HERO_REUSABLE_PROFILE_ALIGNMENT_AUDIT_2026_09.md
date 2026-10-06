# KAORI Hero Reusable Profile Alignment Audit — September 2026

## Result

Hero Standard v1.6 upgrades KAORI from shared visual primitive ownership to explicit reusable profile ownership for same-context families, beginning with the paired Operational Dashboard family.

The visual Hero baseline is unchanged. This change is architectural and semantic: one profile renderer now owns the full dashboard Hero grammar while domain templates provide values only.

## Baseline

Previous Hero Standard v1.5 correctly centralized geometry, typography, Violet surface, dark mode, context tiles, status badges, and action styling in `app/templates/components/page_hero.html`. However, page and family templates could still compose the shell from low-level macros, allowing semantic drift while remaining visually compliant.

Confirmed drift before v1.6:

- Kubernetes and Object Storage dashboards assembled separate Hero shells and used different right-side context semantics (`Signal Sources` vs `Data Authority`).
- Dashboard action roles diverged between integration/readiness management and generic inventory navigation.
- Object Storage Analytics could render only two Normal metadata items when `inventory_observed_at` was absent.
- The Hero verifier discovered canonical primitive consumers but did not explicitly protect same-context family parity.

## v1.6 decisions

### Profile and state

Hero role and operational condition are separate concepts:

- Hero Profile describes the page role.
- Hero State describes `normal`, `blocked`, or `degraded`; Landing remains an explicit profile exception.
- Same Profile + same State must produce the same structural Hero grammar.

### Operational Dashboard profile

`page_hero.operational_dashboard(...)` is the first full family profile renderer.

It owns:

- Hero shell and responsive layout;
- identity/eyebrow/leading icon;
- title and description typography;
- exactly three Normal metadata slots;
- right context panel;
- `Active Scope` metric;
- `Data Authority` metric;
- blocked-state presentation;
- one source/readiness-management action.

Kubernetes and Object Storage dashboard templates no longer assemble Hero shell/layout/context geometry locally.

### Dashboard semantic parity

Both domains now use the same right-side semantic roles:

1. Active Scope;
2. Data Authority = Committed Snapshots.

The action role is operational source/readiness management. Domain-specific labels and routes remain allowed because they carry the same role.

### Object Storage Analytics metadata

Normal Object Storage Analytics uses three stable metadata roles. The third slot is `Committed Snapshot Boundary`, which states the request-time evidence model rather than fabricating an observation timestamp. Blocked branches may reduce metadata according to the global state exception.

## Ownership and compatibility

Low-level `page_hero` macros remain active compatibility primitives for families that were already standardized under v1.5. They are no longer considered the preferred ownership boundary when a high-level profile renderer exists.

This avoids a visual redesign or unsafe all-at-once rewrite while still establishing the reusable renderer contract and a migration path. Future same-context families must add/choose an approved profile rather than fork page-local Hero structure.

## Guardrails

`verify_hero_component_standard.py` now protects:

- Hero Standard v1.6 documentation tokens;
- required `operational_dashboard` renderer ownership;
- Dashboard paired-profile consumers;
- absence of local Dashboard shell/context composition;
- Object Storage Analytics stable Normal metadata;
- unmanaged Hero-like local surfaces;
- existing removed-macro and dark-mode ownership rules.

`verify_operational_dashboard_standard.py` now protects the same Dashboard profile parity while retaining the dashboard data-boundary, authorization, accessibility, composition, snapshot semantics, release-evidence, and quality-gate checks.

## Classification after remediation

| Area | Before | After |
|---|---|---|
| Hero visual system | PASS | PASS |
| Shared primitive ownership | PASS | PASS |
| Operational Dashboard reusable ownership | Major Drift | PASS — canonical profile |
| Kubernetes/Object Storage Dashboard semantic parity | Major Drift | PASS |
| Object Storage Analytics Normal metadata | Major Drift | PASS |
| Global compatibility families | v1.5 primitive ownership | Accepted migration boundary |
| Hero guardrail | Semantic blind spot | Strengthened |

## Review boundary

No Hero geometry, typography, Violet identity surface, dark-mode behavior, context metric limit, or accessibility baseline was intentionally redesigned. UAT should therefore focus on parity and semantic correctness rather than a new visual style.

Review the following states in staging:

- Kubernetes Dashboard Normal;
- Kubernetes Dashboard Blocked/no cluster;
- Object Storage Dashboard Normal;
- Object Storage Analytics Normal with and without an inventory observation timestamp;
- representative existing v1.5 Hero families to confirm no shared primitive regression.
