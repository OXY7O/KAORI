# KAORI Controlled Refactor Roadmap

## Objective

KAORI remains a modular monolith while domain ownership, test evidence, and dependency direction are strengthened. Microservice extraction is deferred until the relevant module has a stable contract, independent data ownership, and measurable scaling pressure.

## Batch 1 — Foundation Gate and Legacy Cleanup

Status: implemented by the foundation-quality patch.

Scope:

- mandatory CI quality workflow;
- release blocked by quality workflow;
- architecture dependency guard;
- migration graph guard;
- tracked-source hygiene guard;
- Git-based source archive;
- stale foundation cleanup script repaired;
- unused Inventory facade removed;
- unused Integrations compatibility re-export removed;
- wildcard Prometheus evidence export removed;
- empty generic helper and JavaScript placeholders removed.

Exit criteria:

- all static contract tests pass;
- full tests pass in the KAORI Dev Container/CI;
- production image builds after all gates.
- strict Ruff gate passes with zero configured diagnostics and no temporary lint baseline.

## Batch 2 — Integration Ownership

Status: first ownership cutover implemented; post-cutover quality cleanup completed; remaining presentation/resolver edges are tracked.

Implemented in this slice:

- Prometheus runtime, compatibility, query-profile audit, and binding validation moved behind canonical provider operations;
- Alertmanager runtime health and binding validation moved behind canonical provider operations;
- binding creation and selector mutation use provider-neutral registry operations;
- provider packages no longer import their corresponding web/domain packages;
- shared binding orchestration no longer imports WTForms or provider services;
- architecture and contract guards prevent reciprocal imports from returning;
- the post-Batch-2 cleanup removed the temporary 260-diagnostic Ruff debt ceiling and restored strict lint enforcement.

Remaining before package-path movement:

- characterization tests with database/provider fakes for source selection and transaction behavior;
- move source-resolution persistence behind provider application contracts;
- remove remaining integration-to-provider presentation imports;
- remove Kubernetes adapter reverse imports into cluster and inventory modules.

Target:

```text
app/integrations/core/
app/integrations/providers/kubernetes/
app/integrations/metrics/
app/integrations/providers/alertmanager/
```

Required sequence:

1. Add characterization tests for source resolution, validation, binding, and runtime-state persistence.
2. Define provider-neutral commands and result contracts.
3. Move Prometheus provider implementation behind one canonical application boundary.
4. Move Alertmanager provider implementation behind one canonical application boundary.
5. Keep existing routes as thin HTTP adapters during cutover.
6. Remove reciprocal imports and compatibility modules.
7. Update architecture debt baseline as cycles shrink.

Do not move package paths before behavior and import contracts exist.

## Batch 3 — Analytics Alerts Pilot

Status: structural decomposition, typed normalized contracts, provider-failure characterization, Alertmanager exception normalization, and typed health, routing, silence, and inhibition presentation contracts are implemented.

Implemented:

- the 4,637-line Alerts service was split by responsibility;
- interactive orchestration moved to `application.py`;
- dashboard/report snapshot orchestration moved to `snapshots.py`;
- provider I/O and payload normalization moved to focused source modules;
- routing, silences, inhibition, ownership, readiness, and signal composition now have explicit owners;
- all known internal consumers use canonical focused modules;
- the temporary `service.py` compatibility façade has been removed;
- characterization and architecture contracts protect the existing behavior and dependency direction;
- canonical `NormalizedAlert`, `AlertSourceStatus`, `AlertLoadResult`, and `AlertsSnapshot` contracts now protect internal boundaries.
- controlled-fake tests now freeze explicit-source behavior, automatic fallback, combined failures, malformed payload handling, and provider exception boundaries;
- unexpected Alertmanager exceptions now become canonical source diagnostics, trigger Prometheus fallback in `auto` mode, and remain isolated for explicit Alertmanager selection;
- source-health, integration-status, routing-group, and routing-summary dictionaries now have focused canonical contracts while preserving their runtime shapes;
- Alertmanager silence API status, normalized silence matchers, silence rows, silence summaries, inhibition rows, and inhibition summaries now have focused canonical contracts while preserving matcher and visibility behavior.

Remaining in Batch 3:

1. Continue replacing broad presentation dictionaries, next with ownership and incident-readiness summaries.
2. Add canonical provider diagnostic codes without changing user-facing wording.
3. Continue decomposing oversized Analytics services behind characterization tests.

Do not combine typed-contract migration with a behavioral redesign of alert scoring or routing semantics.

## Batch 4 — Canonical Analytics Snapshots

Provider queries should produce reusable snapshots consumed by:

- interactive analytics pages;
- reports;
- intelligence;
- scheduled exports;
- future automation decisions.

Reports must not reimplement live Prometheus queries when a canonical snapshot is available.

## Batch 5 — Route and Job Simplification

- move transaction ownership into application services;
- pass actor/settings explicitly instead of using Flask globals;
- centralize job status, cancel, and dismiss lifecycle;
- split Celery entrypoints from orchestration and persistence;
- introduce retryable and non-retryable error taxonomy.

## Batch 6 — Reusable Data UI and JavaScript Lifecycle

- standardize table blocks, pagination, filter toolbars, empty states, and modal shells;
- move inline JavaScript to idempotent static modules;
- register behavior through DOM and HTMX lifecycle hooks;
- add cleanup for replaced elements;
- preserve domain-specific wording and rules locally.

## Refactor Safety Rules

1. One domain or responsibility per commit.
2. Characterization tests before behavior-preserving refactors.
3. No package move and behavior change in the same commit.
4. No compatibility layer without an owner, removal date, and contract test.
5. No new generic `helpers.py` or universal client/service.
6. Update documentation and the debt baseline in the same commit.
7. Run the full quality gate before merge.
