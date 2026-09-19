# KAORI Reports Storage Workspace Final Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize Reports Storage as a concise operational workspace, shorten Reports generation copy, and add canonical icons to key Reports sections without changing storage execution ownership.

**Architecture:** Keep all existing storage service/runtime contracts, including worker-owned strong verification and read-only integrity scanning. Redesign the Jinja presentation around explicit Storage Posture, Storage Target, Access & Readiness, Artifact Coverage, Governance Boundary, Integrity Posture, Verification Actions, Latest Verification, and Reference Integrity sections. Preserve global KAORI hero metadata maximum of three labels and existing lifecycle ownership.

**Tech Stack:** Flask/Jinja, HTMX, Tailwind utility classes, Lucide icons, pytest static contracts.

**Spec:** Approved in-chat KAORI Reports Storage redesign on 2026-08-26.

## Global Constraints

- Hero metadata: maximum 3 labels.
- Strong backend verification remains worker-owned; web rendering performs no provider write probe.
- Artifact integrity scan remains read-only.
- Lifecycle mutation remains owned by Platform Operations → Data Lifecycle.
- Use existing KAORI semantic tokens and Tailwind patterns only.
- No new database schema or migration.

---

### Task 1: Lock the new Reports presentation contracts

**Files:**
- Create: `tests/contracts/reports/test_reports_storage_workspace_final_redesign_20260826_contract.py`
- Modify: existing storage/report UI contract tests only where they assert superseded copy/layout.

- [ ] Write failing static contracts for new Storage Overview/Integrity structure, compact copy, icons, and hero max-three behavior.
- [ ] Run the targeted contract test and confirm it fails on the old layout.
- [ ] Keep tests focused on observable presentation contracts rather than incidental Tailwind classes.

### Task 2: Redesign Storage Overview and Integrity workspace

**Files:**
- Modify: `app/templates/reports/storage/index.html`
- Modify: `app/templates/reports/storage/_verification_status.html`
- Modify: `app/reports/storage/service.py`

- [ ] Replace overview configuration-dump hierarchy with Storage Posture, Storage Target, Access & Readiness, Artifact Coverage, and Governance Boundary.
- [ ] Replace horizontal-scroll object-key presentation with a readable wrapped contract plus copy action.
- [ ] Replace integrity duplication with Integrity Posture, two concise verification action cards, Latest Verification, and Reference Integrity.
- [ ] Keep retained-reference exception table conditional on actual samples.
- [ ] Shorten the Reports Storage subtitle without losing PDF/XLSX/CSV context.
- [ ] Run storage contracts and verify green.

### Task 3: Tighten Reports copy and section icon hierarchy

**Files:**
- Modify: `app/reports/generate/service.py`
- Modify: `app/templates/reports/overview/partials/_reporting_estate_capability.html`
- Modify: `app/templates/reports/schedules/index.html`

- [ ] Shorten Generate Report subtitle.
- [ ] Add `workflow` icon to Contracts & Automation.
- [ ] Add `calendar-clock` icon to Schedule Registry heading.
- [ ] Add `history` icon to Recent Schedule Runs heading.
- [ ] Run relevant Reports contracts and hero verifier.

### Task 4: Verification and packaging

**Files:**
- Package changed files only relative to current cumulative KAORI workspace.

- [ ] Run targeted pytest contracts.
- [ ] Parse modified Jinja templates.
- [ ] Compile modified Python.
- [ ] Run existing KAORI hero, architecture/report generation verifiers available in the workspace.
- [ ] Package final changed files into ZIP and calculate SHA-256.
