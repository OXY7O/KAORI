# Integrations Full Workspace Audit — 2026-08-07

## Scope

This audit covers the currently implemented Integration surfaces:

- Integration Overview;
- Kubernetes Integration registry and all detail tabs;
- Prometheus registry and all detail tabs;
- Alertmanager registry and all detail tabs;
- shared Runtime History / Recent Runtime Observations;
- native Integration dialogs;
- operational toast lifecycle used by Integration mutations.

The review is based on the KAORI Inventory/Analytics visual grammar and the current Integration semantic contracts. The goal is not to make provider workspaces identical: shared geometry is reusable while provider-specific evidence remains explicit.

## Findings and resolution

### 1. Light / dark mode

**Finding:** several Integration identity icons and brand context labels used the light-mode Violet treatment without an explicit dark-mode Lavender treatment. Some framed workspace tab text also retained the light treatment.

**Resolution:** identity icon ownership now uses brand tokens with `dark:text-kaori-accent` / `dark:border-brand-outline` where the identity element requires explicit contrast. Normal surfaces remain tokenized (`surface-card`, `surface-subtle`, outline tokens). Semantic colors remain state-only.

Repository verification:

```text
python scripts/verify_dark_mode_standard.py
```

must pass before the patch is accepted.

### 2. Operational toast countdown

**Finding:** self-dismissing toasts could disappear while their small countdown bar remained static, especially for HTMX/OOB inserted feedback.

**Root cause:** the previous width transition was started before the browser reliably committed the initial width for dynamically inserted nodes.

**Resolution:** `operational_toasts.js` now owns countdown animation with Web Animations API and a forced-layout transform fallback. Pause/resume and manual dismissal cancel/restart the same stateful countdown rather than recreating a visual-only timer.

### 3. Content alignment / spacing

**Finding:** several provider right rails and evidence headers became visually dense after multiple incremental redesigns. Compact labels could wrap onto two lines, making status placement look misaligned.

**Resolution:** compact label primitives are single-line by default, owning layouts keep status chips `shrink-0`, Kubernetes decision rails retain their widened proportions, and provider bound-scope tables are no longer squeezed beside decision rails.

### 4. Code errors

**Finding:** Kubernetes detail failed with:

```text
ImportError: cannot import name 'runtime_observation_state_view'
```

**Resolution:** the shared runtime presentation module again exports `runtime_observation_state_view(...)`. The helper intentionally keeps Connection State separate from persisted Runtime Health. No observation returns `Not Observed`, never a synthetic `Healthy` state.

The internal import verifier is part of the regression gate:

```text
python scripts/verify_internal_import_symbols.py
```

### 5. Recent Runtime Observations View More

**Finding:** K8s/Prometheus/Alertmanager runtime-history detail presentation drifted between expandable rows and dialogs. HTMX filter swaps also previously caused stale expanded-row state.

**Resolution:** one shared native modal now owns `View More` for all three providers. The shared runtime history only renders the compact table; one modal per visible observation is rendered outside the table. Native dialogs are opened by the reusable `native_dialogs.js` controller.

### 6. Prometheus / Alertmanager bound scopes

**Finding:** binding tables were constrained inside a main-plus-sidebar grid, reducing room for selectors, validation state, effective resolution, and actions.

**Resolution:** Bound Kubernetes Scopes / Bound Operational Scopes are now full-width sections. Consumer Resolution and Binding Decision remain in the split layout below them.

### 7. Compact labels

**Finding:** some compact labels rendered word-over-word when the surrounding column became narrow.

**Resolution:** `status_label`, `status_indicator_label`, `special_label`, and normal `metadata_label` content are nowrap by default. Explicit wrapping is still supported for long technical metadata via `wrap=true`.

### 8. DRY / reusable ownership

The audit consolidates cross-provider behavior into shared owners:

```text
components/table_label.html                          semantic/metadata labels
integrations/components/_workspace.html              Integration geometry / identity icons
integrations/components/_semantic_status.html        provider semantic adapter
integrations/components/_runtime_observation_modal.html shared runtime detail
integrations/partials/_runtime_history.html           shared runtime-history table/filter/pagination
static/js/native_dialogs.js                          native dialog lifecycle
static/js/operational_toasts.js                      toast countdown/dismiss lifecycle
```

Provider templates only supply provider-specific evidence and route/action context.

## Semantic invariants preserved

```text
Connection State != Runtime Health
Runtime Health != Validation Readiness
Source Readiness != Binding Validation != Effective Resolution
Prometheus endpoint/runtime profile != Prometheus query capability/retention contract
Alertmanager API readiness != downstream consumer binding readiness
```

No UI refactor is allowed to collapse those states merely to simplify presentation.

## Regression checklist

- [ ] Integration Overview works in light and dark mode.
- [ ] Kubernetes Overview + Configuration + Validation + Runtime + Inventory work in light and dark mode.
- [ ] Prometheus Registry + all detail tabs work in light and dark mode.
- [ ] Alertmanager Registry + all detail tabs work in light and dark mode.
- [ ] self-dismissing toast countdown visibly advances and pauses/resumes correctly.
- [ ] K8s detail imports runtime presentation without error.
- [ ] Recent Runtime Observations opens one centered modal on all three providers.
- [ ] Runtime filters close naturally because dialogs are not persisted across HTMX swaps.
- [ ] Prometheus and Alertmanager bound-scope tables are full width.
- [ ] compact labels remain one line unless explicit metadata wrapping is requested.
- [ ] no Integration template introduces inline `onclick`, `onchange`, or `onsubmit` handlers.

## Verification result

After reconciliation, `scripts/verify_ui_style.py` reports no Integration/Prometheus/Alertmanager-specific style-baseline drift. Remaining findings belong to Analytics, Notifications, or Reports and are outside this Integration audit scope.
