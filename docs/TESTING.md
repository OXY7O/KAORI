# KAORI Testing

KAORI uses a layered release test strategy covering contracts, migrations, unit, functional, integration, security, rendering, and end-to-end evidence. The canonical release entry point is:

```bash
python scripts/verify_final_release.py --all --runtime
```


## Practical test commands

Use the narrowest owning test first, then broaden the evidence before release.

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
