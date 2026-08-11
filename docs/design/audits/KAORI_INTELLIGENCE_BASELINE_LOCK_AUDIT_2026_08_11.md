# KAORI Intelligence Baseline Lock Audit — 2026-08-11

## Decision

Intelligence is approved for a **baseline lock** while feature delivery remains in progress.
This is intentionally narrower than a feature-complete release declaration.

## Reviewed

- Recommendations routes, HTMX ownership, pagination, and side-drawer detail.
- Rule Catalog filtering, inline adjacent detail, status semantics, and canonical definitions.
- Alert Intelligence source ownership and Reserved Plan boundaries.
- Automation Control permission boundaries and default fail-closed mutation gate.
- KAORI Violet/shared UI ownership, dark mode, application shell, and first-party JavaScript.
- Existing Intelligence contract suite; stale source-format fingerprints were replaced with
  semantic assertions.

## Findings

1. No Intelligence-specific UI style/reuse debt is reported by the global verifiers.
2. All user-facing Intelligence GET routes require `intelligence.view`.
3. Automation Control mutations are disabled by default through
   `AUTOMATION_CONTROL_MUTATIONS_ENABLED`, and no environment-configured enablement is
   exposed by the current Config baseline.
4. Server and HCI alert-enrichment sources remain explicitly Reserved Plan.
5. Three existing contract failures were stale formatting/signature fingerprints rather
   than runtime regressions and were normalized without weakening the intended contract.

## Deferred

Automation mutation behavior and unfinished Server/HCI provider paths are not declared
feature-complete. They must remain fail-closed/Reserved Plan until their dedicated release
evidence is implemented.
