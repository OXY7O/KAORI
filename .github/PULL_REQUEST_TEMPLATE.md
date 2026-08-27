## Linked Issue

Closes/Relates to #

## Scope Summary

Describe the governed scope of this change and what is intentionally out of scope.

## Acceptance Criteria Coverage

Map each linked acceptance criterion to implementation evidence.

## Test Evidence

List targeted and full validation executed. Include relevant GitHub Actions run evidence when available.

## Security Impact

State the security impact, threat-boundary changes, or `None` with rationale.

## Migration / Data Impact

State schema, migration, compatibility, or retained-data impact, or `None` with rationale.

## Observability / Operational Impact

State logging, metrics, alerts, operational workflow, rollback, and support impact where applicable.

## UAT

- [ ] Not yet applicable — work branch integration only.
- [ ] Integrated into `kaori/staging` and full staging CI passed.
- [ ] Local UAT from `kaori/staging` passed and explicit acceptance is recorded.

A change is not `Done` merely because code and CI are complete. Promotion from `kaori/staging` to `main` requires explicit local UAT acceptance.

## Release Impact

State release target/milestone impact, compatibility notes, and whether release documentation must change.

## Reviewer Checklist

- [ ] Change matches the linked work item and agreed scope.
- [ ] Acceptance Criteria are covered by implementation and evidence.
- [ ] Required CI is green without suppressed failures.
- [ ] No unexpected skipped tests, tracebacks, assertion failures, HTTP 5xx responses, or migration/runtime failures remain unexplained.
- [ ] Generated frontend artifacts are reproducible when applicable.
- [ ] Security and migration impacts are explicitly addressed.
- [ ] Documentation and contracts are aligned.
- [ ] `kaori/staging` UAT evidence is present before staging-to-main promotion.
- [ ] Merge strategy to `main` remains merge commit.
