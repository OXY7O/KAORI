# KAORI Testing

KAORI uses a layered release test strategy covering contracts, migrations, unit, functional, integration, security, rendering, and end-to-end evidence. The canonical release entry point is:

```bash
python scripts/verify_final_release.py --all --runtime
```


## Reading Developer Check and Full Admission coverage

**A small number of green gate rows does not mean only that many tests were run.** Each named verifier may inspect many modules, functions, templates, revisions and source contracts. Developer Check lists only checks **actually selected by changed-path routing**, including exact commands, elapsed durations, executed outcomes and the focused pytest path selection in the GitHub Step Summary. A check not selected is NOT RUN, not PASS. Do not divide selected-check counts by application domains as a proxy for coverage.

Full Admission owns the comprehensive release suite. Its Static & Governance execution summary enumerates individual existing verifiers and links to the short-lived, complete per-verifier log artifact even after success. The release-surface registry is a distinct source-registration inventory, not a test result. Executed tests are counted by pytest/JUnit and taxonomy; security scans, frontend build/verification and Runtime & DAST are separate outcome/evidence boundaries. A green Developer Check never replaces the frozen-candidate Full Admission or human UAT.

Keep established `verify_*` file names and contract test modules as canonical programmatic identities until a complete reference/compatibility migration is separately authorized. Prefer precise human-readable labels and exact source commands in CI output to renaming scripts only for appearance. The regular release CLI's quiet PASS and detailed FAIL remain in force.

## Practical test commands

Use the narrowest owning test first, then broaden the evidence before release.

### Developer Check validation plan

Before running broader development validation, resolve the same changed-path plan used by GitHub Actions:

```bash
python scripts/developer_check_plan.py --base kaori/staging --head HEAD
```

The planner is the path/test-selection authority for both Local-First Dev Container work and GitHub Developer Check. It classifies direct capability impact, preserves existing shared/contract widening, and returns deterministic focused pytest paths. Unknown or shared impact widens rather than silently omitting coverage.

Capability-aware routing includes `app/kubernetes/tenant/**` (Tenant behavior and Tenant-owned Kubernetes contracts), `app/artifact_registry/**` and `app/templates/artifact_registry/**` (Artifact Registry behavior/UI and owning `tests/unit/artifact_registry` plus `tests/contracts/artifact_registry`), and `app/storage/object_storage/**`, `app/templates/storage/object_storage/**`, and domain-owned frontend assets (Object Storage behavior/UI and `tests/contracts/storage/object_storage`). Changes to Registry/Harbor and Object Storage integration adapters retain Integration tests **and** select their affected operational-domain contracts. Direct `tests/contracts/artifact_registry/**` changes are part of the canonical contract-family routing, not generic release-only fallback.

These are **focused Developer Check** selections; they do not replace canonical source-wide static/domain verifiers or the complete Full Admission suite at the frozen-candidate boundary. When a path has shared or unknown blast radius, retain existing widening/fail-closed behavior. The release-surface verifier checks that every declared contract evidence path contains executable `test_*.py` modules; successful Static & Governance logs enumerate the release surfaces and their test-module counts.

### Incremental Draft validation (issue #1801)

The canonical Developer Check planner emits `template_paths` and a `template_scope` decision. File-scoped `djlint --check` applies only to **existing, safe, owned leaf HTML templates** under Access, Artifact Registry, Integrations, Intelligence, Kubernetes Tenant, Platform Operations, Reports, Settings, Object Storage, and Welcome, as defined by the canonical planner's `_LEAF_TEMPLATE_PREFIXES` and ownership routes. The planner also selects relevant capability behavior and contract regression tests; shared, unknown, removed, and unsafe template paths widen to full lint and broad contracts. The Object Storage leaf UI path selects `tests/storage/object_storage` and owning contracts rather than unrelated Storage test folders.

Changes to shared template/layout components, unrecognized ownership, removed templates, CI/test authority, or conflicting mixed paths widen to full `app/templates` lint and applicable broad contract tests. A non-authority Markdown-only diff (such as `README.md`) skips CI image/toolchain preparation and heavy validation jobs: the cheap `Route Checks` plus fail-closed `Developer Check` aggregate still execute. CI/security/release/engineering authority docs are deliberately treated as wide changes, not ordinary documentation.

Known leaf-template owners now include Access, Integrations, Intelligence, Platform Operations, Reports, Settings, Welcome, Artifact Registry, Object Storage and Kubernetes Tenant. Domains without proven template ownership continue to use broad lint and contract coverage; the planner does not infer ownership from arbitrary filenames.

For fast local troubleshooting on a **large, already-reviewed candidate**, inspect the latest repair delta without changing the canonical PR-base validation authority:

```bash
python scripts/developer_check_plan.py --base HEAD~1 --head HEAD
```

Run only the selected pytest paths during the repair loop. This command is **diagnostic local feedback only**: PR Developer Check against the actual staging base and frozen-candidate Full Admission remain mandatory. Never use a last-commit delta as final admission evidence.

### Early Visual QA impact route

Welcome content, the shared Hero/layout, global CSS, and application-shell theme changes may invalidate deterministic visual baselines. The planner now selects **only the existing Welcome visual test** at `tests/ui/test_representative_interactions.py::test_welcome_visual_qa_light_and_dark` on those changed-path families and when its baseline manifest or visual-audit helper changes. This runs the existing canonical six-viewport light/dark test under Draft focused pytest rather than discovering a hash mismatch after lengthy Full Admission functional tests. It does not rebaseline, omit any device/theme, or replace the comprehensive browser tests. Changes unrelated to those visual surfaces do not select this focused Playwright check.

Exact-head Full Admission #38798164894 demonstrated the failure mode: 3,106 other functional cases PASS but `welcome-light-mobile` visual hash FAIL after 14m43s of functional test execution. Incident investigation and human-reviewed baseline authority remain tracked under #2196; an actual hash difference is not proof of an acceptable visual change.

This is a **Draft and Pre-Ready cost optimization**; the frozen Ready candidate still undergoes the existing exact-head Developer Check and complete Full Admission. Existing source-wide evidence reuse is restricted to identical source-tree and validation-authority fingerprints with validated lineage. No cross-source-tree or per-domain admission evidence reuse is enabled. The tracked measurement and feasibility issues are #1796 and #2194. An unexecuted plan is not test PASS.

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

**Engineering Quality profiling (#2339):** Successful Static & Governance job logs report one bounded elapsed-time line for each of the 18 existing Engineering Quality checks (Ruff, djLint, Pyright, import/architecture/code-health verifiers). The Foundation and Domain groups retain their quiet per-command success output, and all groups retain their existing aggregate counts and diagnostics. Compare the same verifier across successful exact-head runs on the same runner; distinguish command time from the independent Contract & Migration Safety pytest and from GitHub queue wait. The per-command timing is observability only—not an optimization or permission to suppress a required check.

**Pyright phase breakdown (#2358):** On a successful Full Admission Static & Governance check, Pyright runs with its supported `--stats` option, retaining the same `--project pyrightconfig.json`, basic checking mode, scope, exit code and type diagnostics. The existing static capture helper prints only the final 24 lines of the successful Pyright diagnostic log, including analysis statistics where present, while retaining its full raw output internally. Draft Developer Check retains its original Pyright invocation. Compare file-count and analysis phase timing against the observed Pyright command wall time (Draft 145s, Ready 138s) before proposing caching/parallelism; stats are measurement, not runtime acceleration.


### Functional and security behavior

```bash
bash scripts/quality_gate.sh --tests
```

The full Functional Tests pytest invocation records the **15 slowest test durations** using pytest's existing `--durations=15` option (#2232). It uses the same test selection, fixtures, JUnit `release-suite.xml`, and `run_pytest_capture` diagnostic logs — **no second test run or new profiler**. On a **successful** Full Admission, download the compact `full-admission-functional-timing-<run-id>-<attempt>` artifact (retained for 3 days) and inspect `functional-tests.*.log` for the `slowest durations` section; the existing `Upload Test Diagnostics` artifact continues to retain broader evidence **only on failure**. The success artifact contains just the pytest log, not browser screenshots, traces, or complete test-output directories. Distinguish test setup/call/teardown timing from job queue delay, `npm ci`, CSS setup and runner-resource overhead, which require separate job/log/host measurements. Profiling is observational, not a speedup or permission to suppress slow tests.

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

## Reviewed visual fingerprint and raster stability

The Playwright Visual QA gate remains strict on viewport geometry and the committed `tests/ui/baselines/authenticated-visual.json` manifest. Normal captures compare the existing 128px blurred/24-unit quantized screenshot digest exactly. The proposed #2196 stabilization recognizes **only a one-channel, one-thumbnail-pixel flip at the 8-bit near-white 251/252 quantization boundary**, when correcting that exact channel reproduces the **existing reviewed SHA256**. It emits a warning so the exception remains auditable; two changed channels, non-white changes, geometry mismatches, and missing/changed manifests remain FAIL. There is no baseline regeneration, test skip or change to acceptance authority.

This limited guard is motivated by official runs #38792762830 (baseline PASS) and #38798164894 (same visual source and runner, baseline FAIL): the raw screenshots have identical 390×844 geometry, only 108 of 329,160 pixels differ by at most 2 RGB units, and the quantized thumbnail differs at exactly one channel (240→255) when 251 rounds to 240 versus 252 rounds to 255. The actual and expected images were reviewed against their official retained artifacts. Negative regression cases must prove that meaningful visual changes remain blocked.

**Status:** the guard is a proposed visual QA policy adjustment under #2196 until source/CI validation and explicit human review. Do not interpret a Draft PR or a local pixel comparison as Full Admission PASS.

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
