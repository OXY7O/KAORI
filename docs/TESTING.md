# KAORI Testing

KAORI uses a layered release test strategy covering contracts, migrations, unit, functional, integration, security, rendering, and end-to-end evidence. The canonical release entry point is:

```bash
python scripts/verify_final_release.py --all --runtime
```


## Scenario-driven QA and UAT acceptance

This section owns the reusable **scenario specification and execution-record contract** for KAORI. It extends, rather than replaces, the test taxonomy in `tests/README.md`, the Playwright/Visual QA authorities (#222/#543), and the immutable delivery/UAT workflow. ISO/IEC/IEEE 29119 test documentation, risk-based testing, and Given/When/Then are design references, not a requirement to install another test runner.

**One specification can be executed many times; one execution belongs to one candidate and environment.** Machine test outcomes are not human acceptance decisions. A green source gate proves its selected automated assertions, not that every product scenario was exercised or a human accepted the product.

### Reusable scenario specification

Record the following once per scenario, and maintain it when the capability contract changes:

| Field | Required specification |
| --- | --- |
| Scenario identity | Stable, capability-owned ID (for example `UAT-TEN-001`), concise title, owning Issue/requirement and affected capability |
| Classification | Positive or negative and applicable boundary, authorization, failure, recovery, or state-transition dimension |
| Risk and purpose | Concrete product/operational invariant and why the outcome matters; prioritize provider writes, access, persistence, secrets, and misleading success |
| Preconditions | User/role, fixture, environment, provider availability and baseline object identities or committed state |
| Action | Human-reproducible steps or Given/When/Then behavior, including clicks/inputs or service/API calls |
| Expected result | Observable UI/API response **and** applicable KAORI committed state, external authoritative provider state, security boundary and Audit evidence |
| Execution mapping | One or more owning pytest/Playwright node IDs or existing suite paths, plus an explicit human-only/real-provider gap when automation cannot prove the expectation |
| Isolation | Test identities, fixture setup, allowed provider mutation, cleanup/read-back and required safeguards |

A scenario ID is a **traceability identifier**, not a pytest marker, new directory taxonomy, Project field, or alternative CI result vocabulary. Keep scenario ownership in the existing capability test suite; link implementation tests in the owning Issue/PR. Use the existing `tests/ui/` Playwright harness for browser interactions, not an additional JavaScript/Cucumber runner.

For a mutable operation, cover a representative positive flow and risk-relevant negative flow(s), including rejected authorization/invalid identity/stale preflight, no unintended provider or database side effects, and no false success. For read-only or low-risk behavior, document why a classification is inapplicable instead of manufacturing tests. Include boundary and failure/recovery scenarios where operational impact warrants them. No blanket numeric pass or coverage percentage replaces this risk decision.

For UI changes, executable assertions should cover real interactions (navigation, click, fill/select, validation, submit, HTMX updates, dialogs, filters, pagination, feedback and outcome) together with applicable Violet/shared-component invariants, light/dark, viewport, keyboard, blocked/degraded/empty states and post-interaction screenshots. Reuse the #543 visual inventory, reviewed baselines and six canonical viewports; a correct screenshot alone does not establish functional correctness, and a visual baseline alone does not establish good design.

For non-UI mutations, verify transaction boundaries, authorization, persistence, audit/correlation and provider pre/post state. Deterministic fake-provider PASS must be identified as **simulated** evidence; do not present it as a real-provider UAT pass. External provider mutation requires an approved isolated/disposable fixture or separately governed operator approval, cleanup, read-back and recovery procedure.

### Example scenario pair — Native Namespace adoption

The following are **specification examples**, not claims of UAT execution or proof that these paths have passed. Use the currently approved Tenant (#125) and provider-adoption contract when implementing executable tests.

**`UAT-TEN-001` — Positive: adopt an existing Native Namespace**

```gherkin
Given an existing Kubernetes Namespace is not governed by KAORI
And a permitted operator completed a fresh identity-bound Preflight
When the operator confirms adoption of the verified Namespace
Then exactly one matching adopted Namespace generation is committed
And the provider identity remains authoritative and unchanged except for explicitly approved writes
And Activity Audit correctly reports the performed operation
```

**`UAT-TEN-002` — Negative: reject a stale Native Namespace Preflight**

```gherkin
Given a Namespace was discovered using its verified UID and resourceVersion
And its resourceVersion changed after Preflight
When the operator submits the stale adoption request
Then KAORI rejects the stale operation with actionable feedback
And no new adopted Tenant or Namespace state is committed
And no unauthorized provider mutation or false-success audit is produced
```

Both scenarios may map to multiple existing tests: browser actions and messaging, domain/service validation, database/audit persistence, security authorization, and controlled provider read-back. A UI PASS is not a substitute for database/provider assertions.

### Per-run execution record

For **every actual execution**, retain a record separate from the reusable specification:

| Field | Required execution evidence |
| --- | --- |
| Identity | Scenario ID and version/reference, relevant test node IDs, linked Issue/PR and findings |
| Candidate | Source commit SHA and source tree SHA; validation profile/authority when reused; OCI digest and release identity for server-deployed UAT |
| Environment | Local DevContainer versus `kaori/staging`/UAT, target URL where relevant, provider kind and simulated versus real-provider boundary |
| Execution | Test runner or human tester, timestamp, attempt, fixtures/role and actual steps or automated command |
| Result | Actual observation/assertions versus expected result; explicit PASS, FAIL, BLOCKED, NOT RUN, N/A or runner SKIP |
| Evidence | JUnit/test output, browser screenshot/trace, sanitized logs, Activity correlation, DB and provider read-back where applicable |
| Findings and retest | Linked defect Issue, impact, mitigation/retest decision, previous attempt identity and exact fixed candidate |

Interpret execution outcomes as follows:

- **PASS:** the intended scenario ran, applicable assertions were verified and required evidence is attributable to the tested candidate.
- **FAIL:** observed behavior violates an expected outcome. Record the finding and preserve failure evidence.
- **BLOCKED:** the scenario could not safely execute because a prerequisite, provider authority or dependency was unavailable; do not infer product behavior.
- **NOT RUN:** no execution occurred on the selected candidate.
- **N/A:** a scenario/classification is genuinely inapplicable with an explicit reason **accepted by the reviewer**, not a way to bypass an inconvenient test.
- **SKIP:** the runner skipped the test; report this separately from a reviewed N/A. For example, missing `KAORI_UI_BASE_URL` cannot be counted as an executed mandatory browser PASS.

Retried/flaky executions remain separately identifiable and do not overwrite earlier failure evidence. A scenario executed on a different source tree or deployed digest is not interchangeable with the selected candidate. A real external provider UAT requirement remains BLOCKED/NOT RUN until actual authorized provider evidence exists; mocks cannot satisfy it.

Use the **existing JUnit, pytest/Playwright screenshot/trace, CI artifact and Issue/PR evidence paths**. Do not place credentials, kubeconfigs, tokens, secrets, personal data, or sensitive provider material in published artifacts. Keep evidence concise and tied to the source SHA, not just a mutable branch name. Later automated evaluation of mandatory coverage and report generation is owned by #1728; this documentation change does **not** secretly add a new release gate.

### Human acceptance record

Human acceptance is **separate from the machine execution results**. Record it as explicit Issue/PR UAT evidence for the selected candidate:

| Field | Required reviewer record |
| --- | --- |
| Scope | Candidate source SHA/tree and, for server UAT, exact immutable OCI digest; capability, environment and mandatory scenario set |
| Coverage | Executed positive/negative cases, missing/blocked/skipped cases, approved N/A reasons and human-only review |
| Findings | Remaining defects, security/operational risks and remediation/acceptance disposition |
| Decision | Named authorized human reviewer, review time, **accepted / not accepted / pending**, reason and linked evidence |
| Lineage | Any new candidate after a correction requires an impact assessment and repeat of affected tests; never silently reuse invalidated acceptance |

A machine may recommend acceptance readiness but **cannot approve itself or impersonate a human reviewer**. The governing Project Status taxonomy remains unchanged (UAT until the existing completion conditions are satisfied). Do not mark an unfinished or mandatory-SKIP scenario PASS based only on an aggregate pytest/CI exit code.

## Practical test commands

Use the narrowest owning test first, then broaden the evidence before release.

### Developer Check validation plan

Before running broader development validation, resolve the same changed-path plan used by GitHub Actions:

```bash
python scripts/developer_check_plan.py --base kaori/staging --head HEAD
```

The planner is the path/test-selection authority for both Local-First Dev Container work and GitHub Developer Check. It classifies direct capability impact, preserves existing shared/contract widening, and returns deterministic focused pytest paths. Unknown or shared impact widens rather than silently omitting coverage.

Current capability-aware pilot: `app/kubernetes/tenant/**` selects Tenant behavior tests and existing Tenant-owned Kubernetes contracts instead of automatically selecting the entire Kubernetes behavior suite. Full Admission remains comprehensive at the frozen-candidate boundary.

### Targeted regression

```bash
python -m pytest -q tests/contracts/access/test_identity_provider_refinement_contract.py
python -m pytest -q tests/settings/test_system_information.py
```

Replace those paths with the owning domain for the change under review.

### Static quality

```bash
bash scripts/quality_gate.sh --static
```

This includes source hygiene, architecture/final-lock verifiers, literal Jinja template-dependency resolution, Ruff check/format, djLint, Pyright, migration graph, import graph, UI contracts, and contract/migration pytest evidence.

### Functional and security behavior

```bash
bash scripts/quality_gate.sh --tests
```

### Frontend reproducibility

```bash
bash scripts/quality_gate.sh --frontend
```

### Complete source release gate

```bash
python scripts/verify_final_release.py --all
```

### Runtime-aware final gate

```bash
python scripts/verify_final_release.py --all --runtime
```

The runtime-aware gate additionally requires endpoint-registry evidence and a running Reports worker with the expected queue. Run it only against an environment where those runtime prerequisites are intentionally available.

## Failure policy

- Do not use `--fix` as proof that a release is clean; rerun Ruff without mutation after fixes.
- Do not raise debt ceilings, weaken final-lock verifiers, or skip a failing domain to approve a release.
- Every runtime regression should gain the narrowest practical permanent contract or behavior test.
- After auto-formatting, rerun the affected tests because formatter changes can expose brittle template/string contracts.
- Debug tests under `tests/debug/` are diagnostic only and are excluded from release approval.

## Development test dependencies

Development-only test tooling is declared in `requirements/dev.in` and locked in `requirements/dev.txt`. PDF rendering tests use `pypdf` to inspect generated artifacts; it is intentionally not a production/runtime dependency.

After changing either `.in` dependency file, regenerate the lock files inside the Dev Container:

```bash
pip-compile requirements/base.in --output-file requirements/base.txt
pip-compile requirements/dev.in --output-file requirements/dev.txt
```

Rebuild the Dev Container after dependency-lock changes. For an already-running container, install the updated development lock before rerunning the release suite:

```bash
python -m pip install -r requirements/dev.txt
```

## Collection prerequisites

`python scripts/verify_test_prerequisites.py` runs before the full pytest phase. It fails fast when required development test modules are missing or when two `test_*.py` files share the same basename and would collide under pytest's default import behavior.

Tests are organized under `tests/`; `tests/conftest.py` assigns the canonical purpose marker from the top-level test bucket. Debug tests are excluded from release gates, while E2E tests run in their dedicated release phase.


## Functional test module isolation

Functional characterization tests may load isolated application modules, but they must not leak replacements through `sys.modules` into later tests. Prefer `monkeypatch.setitem(sys.modules, name, module)` for every temporary package/module. Direct `sys.modules[...] = ...` or `sys.modules.setdefault(...)` is allowed only for a standalone loader that snapshots the prior registry state and restores it in `try/finally`.

The release prerequisite verifier scans the functional test buckets (`welcome`, `dashboards`, `analytics`, `inventory`, `governance`, and `kubernetes_operations`) and fails fast when it finds a direct module-registry mutation without an explicit restore boundary. This protects application-factory characterization from order-dependent package stubs.
