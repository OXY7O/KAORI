# Reports HTML/PDF Debt Batch Implementation Plan

**Goal:** Resolve remaining #39–#44 Reports HTML/PDF code-health debt in one governed staging candidate while preserving per-family acceptance evidence and avoiding repeated Full Admission cycles.

## Phase 1 — Establish cheap feedback authority
- Finish #68 Developer Check contracts and ensure Draft path-aware checks are green.
- Keep PR #75 Draft while source remains mutable.

## Phase 2 — Characterize current family behavior
For Resource Utilization, Alerts & Anomalies, Forecast Analysis, Analytics Overview, Top Consumers, and Workload Analysis:
- identify current public entrypoint and template-facing presentation keys;
- add focused ownership/characterization contracts before extraction;
- retain existing regression/PDF publication tests as behavioral authority.

## Phase 3 — Family-local extraction
Apply the completed Capacity/Storage pattern one family at a time within the same branch:
- thin stable facade;
- cohesive family package;
- no replacement catch-all;
- no cross-family extraction unless semantics are proven identical.

After each family increment, use Draft Developer Check and targeted report tests. Do not run Full Admission between families.

## Phase 4 — Exact debt reconciliation
- run fresh code-health scanner after all structural changes;
- remove only ledger entries proven stale;
- keep ceilings `800 / 160 / 30 / 8` unchanged;
- broad exception count must not increase.

## Phase 5 — Pre-Ready and final candidate
- collect all remaining findings;
- batch repair;
- require latest Developer Check PASS;
- review complete diff for Critical/Important findings;
- freeze source head;
- mark Ready.

## Phase 6 — Governed Admission and staging
- run one fresh Full Admission for the frozen candidate;
- if it fails, collect all actionable findings, return to Draft, batch repair, and repeat the cheap gate before the next frozen candidate;
- after Full Admission PASS, merge PR #75 to `kaori/staging`;
- verify exact evidence reuse, transition lineage, Fast Smoke, and CI Admission;
- stop at explicit human UAT.

## Evidence bookkeeping
Each child #39–#44 receives a checkpoint comment containing its structural changes, focused tests, fresh scanner result, and staging SHA. Parent #35 records the batch-level admission and staging/UAT checkpoint.
