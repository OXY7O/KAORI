# KAORI Testing

KAORI uses a layered release test strategy covering contracts, migrations, unit, functional, integration, security, rendering, and end-to-end evidence. The canonical release entry point is:

```bash
python scripts/verify_final_release.py --all --runtime
```

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
