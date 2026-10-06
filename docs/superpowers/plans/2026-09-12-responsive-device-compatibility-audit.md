# Responsive & Device Compatibility Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make KAORI's authenticated application shell intentionally adaptive across the canonical viewport matrix, with a mobile app-bar/off-canvas navigation model, mobile-safe overlays, responsive Hero composition, and executable browser contracts.

**Architecture:** Keep desktop behavior and the existing navigation permission model authoritative. Below the desktop breakpoint, remove the persistent sidebar from document flow, use a top-bar menu trigger to control an off-canvas copy of the same canonical navigation, keep page content full-width, and recompose shared Hero/context primitives rather than patch individual pages. Extend the existing Playwright UI authority; do not create a parallel mobile test framework.

**Tech Stack:** Flask, Jinja, Tailwind utility classes, Alpine.js, Playwright, pytest.

**Spec:** GitHub issue #224 and its approved Mobile Product Direction Refinement comment.

## Global Constraints

- Canonical viewports: 1440x900, 1280x800, 1024x768, 768x1024, 390x844, 360x800.
- Mobile resting state has no persistent desktop sidebar.
- Mobile navigation is off-canvas and must not push or shrink page content.
- Document-level horizontal scrolling is prohibited.
- Mobile top bar keeps only primary controls; secondary controls may be hidden or moved without removing necessary access.
- Mobile Hero may simplify to a compact page-intro composition; desktop Hero geometry must not regress.
- No device-specific Samsung CSS; Samsung S24 remains UAT evidence only.
- Reuse existing KAORI Violet tokens, shared navigation permissions, and overlay components.
- Kubernetes Tenant Management (#61, #112–#125) is out of scope.
- Delivery stops at `kaori/staging`; no RC/server deployment/main promotion in this cycle.

---

### Task 1: RED responsive shell contract

**Files:**
- Create: `tests/contracts/release/test_responsive_application_shell_contract.py`
- Modify: none

**Interfaces:**
- Consumes: `app/templates/layouts/app.html`, `components/navigation/sidebar.html`, `components/navigation/navbar.html`.
- Produces: source-level contract proving mobile drawer state, mobile trigger, fixed off-canvas sidebar semantics, full-width mobile content, and desktop-only collapse behavior.

- [ ] **Step 1: Write failing source contract** asserting the shell has independent `mobileNavOpen`, desktop sidebar collapse state, `lg:` desktop sidebar visibility, mobile drawer/backdrop semantics, and no mobile content offset.
- [ ] **Step 2: Run the focused release contract through Developer Check and confirm RED for missing mobile shell authority.**
- [ ] **Step 3: Record the expected RED failure in issue #224.**

### Task 2: Adaptive application shell and navigation

**Files:**
- Modify: `app/templates/layouts/app.html`
- Modify: `app/templates/components/navigation/sidebar.html`
- Modify: `app/templates/components/navigation/navbar.html`

**Interfaces:**
- Consumes: existing `sidebarExpanded`, canonical sidebar menu includes, `kaoriNavbar` Alpine component.
- Produces: `mobileNavOpen` shell state, `[data-mobile-menu-trigger]`, `[data-mobile-navigation]`, `[data-mobile-navigation-backdrop]`, full-width mobile content, desktop sidebar unchanged at `lg+`.

- [ ] **Step 1: Add independent mobile-nav state to the root Alpine shell without reusing desktop collapse persistence.**
- [ ] **Step 2: Keep the canonical sidebar tree but render it as fixed off-canvas navigation below `lg` and persistent sidebar at `lg+`.**
- [ ] **Step 3: Add backdrop and explicit mobile close control; close on Escape, backdrop click, and navigation selection.**
- [ ] **Step 4: Convert navbar's left control to a mobile menu trigger below `lg`, keeping desktop collapse/expand behavior at `lg+`.**
- [ ] **Step 5: Collapse breadcrumb presentation on mobile to the current meaningful page context and reduce action density without removing search, notification, and profile access.**
- [ ] **Step 6: Run the focused contract and confirm GREEN.**

### Task 3: Mobile-safe shared Hero primitives

**Files:**
- Modify: `app/templates/components/page_hero.html`
- Test: `tests/contracts/release/test_responsive_application_shell_contract.py`

**Interfaces:**
- Consumes: shared Hero macros already used by dashboard/inventory/analytics/settings surfaces.
- Produces: mobile-natural Hero height, single-column intro composition, context metrics that stack on compact widths, desktop geometry retained at `lg+`.

- [ ] **Step 1: Extend the RED contract for mobile Hero source classes.**
- [ ] **Step 2: Change shared shell/layout/context metric classes so compact phones avoid fixed tall Hero geometry and two-column metric forcing.**
- [ ] **Step 3: Keep desktop `lg/xl` geometry unchanged.**
- [ ] **Step 4: Run focused contract GREEN.**

### Task 4: Browser responsive interaction coverage

**Files:**
- Create: `tests/ui/test_authenticated_responsive_shell.py`
- Reuse: `tests/ui/conftest.py`

**Interfaces:**
- Consumes: existing authenticated Playwright fixtures and canonical viewport matrix.
- Produces: browser evidence for 390x844/360x800 mobile behavior and desktop regression assertions.

- [ ] **Step 1: Add a failing authenticated browser test asserting desktop sidebar hidden at rest on compact mobile, menu trigger visible, document `scrollWidth <= clientWidth`, and main content remains viewport-safe.**
- [ ] **Step 2: Add drawer open/close assertions for explicit close, backdrop, and navigation selection.**
- [ ] **Step 3: Assert search, notifications, profile/account remain reachable on compact mobile.**
- [ ] **Step 4: Add desktop assertion that persistent sidebar remains visible and desktop collapse control still exists.**
- [ ] **Step 5: Capture screenshots for authenticated shell evidence using the existing UI artifact root.**

### Task 5: Verification and staging integration

**Files:**
- No new production files unless verification exposes a bounded defect.

**Interfaces:**
- Consumes: repository-standard Developer Check and KAORI CI.
- Produces: exact-head branch evidence, PR to `kaori/staging`, and fresh staging Full Admission authority.

- [ ] **Step 1: Run repository-standard formatting/static/contracts/browser checks through Developer Check on the exact final branch SHA.**
- [ ] **Step 2: Review failures; fix only #224 scope, preserving Kubernetes Tenant exclusion.**
- [ ] **Step 3: Open PR to `kaori/staging`, link #224, and complete review/thread/base-drift checks.**
- [ ] **Step 4: Merge with expected-head protection.**
- [ ] **Step 5: Require fresh Full Admission on the exact merged staging SHA.**
- [ ] **Step 6: Record exact staging evidence in #224 and close only when acceptance is satisfied at staging scope.**

## Self-Review

- Spec coverage: shell, navbar, sidebar, Hero, overflow, navigation drawer, responsive viewports, accessibility-relevant labels, browser evidence, and desktop regression are covered.
- Scope exclusion: Kubernetes Tenant Management remains excluded.
- No placeholders or device-specific CSS are introduced.
- Delivery intentionally stops at staging per current maintainer instruction.
