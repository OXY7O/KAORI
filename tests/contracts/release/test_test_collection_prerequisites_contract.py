from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_pdf_reader_dependency_is_owned_by_development_requirements() -> None:
    dev_in = read('requirements/dev.in')
    dev_lock = read('requirements/dev.txt')

    assert 'pypdf==6.14.2' in dev_in
    assert 'pypdf==6.14.2' in dev_lock
    assert 'pypdf' not in read('requirements/base.in')


def test_release_test_preflight_runs_before_full_pytest() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    run_tests = quality_gate.split('run_tests() {', 1)[1].split('run_frontend() {', 1)[0]

    assert 'python scripts/verify_test_prerequisites.py' in run_tests
    assert run_tests.index('verify_test_prerequisites.py') < run_tests.index("pytest -q -m 'not debug and not e2e'")


def test_test_module_basenames_are_unique() -> None:
    by_name: dict[str, list[str]] = {}
    for path in sorted((ROOT / 'tests').rglob('test_*.py')):
        by_name.setdefault(path.name, []).append(str(path.relative_to(ROOT)))

    duplicates = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    assert duplicates == {}


def test_prerequisite_verifier_owns_concise_pass_and_actionable_failures() -> None:
    verifier = read('scripts/verify_test_prerequisites.py')

    assert "print('PASS — KAORI Test Prerequisites')" in verifier
    assert "print('FAIL — KAORI Test Prerequisites')" in verifier
    assert "'pypdf': '6.14.2'" in verifier
    assert 'expected locked version' in verifier
    assert 'install requirements/dev.txt or rebuild the Dev Container' in verifier
    assert 'duplicate pytest module basename' in verifier
    assert 'functional test mutates sys.modules without restore-safe isolation' in verifier
    assert 'use monkeypatch.setitem or explicit try/finally restore' in verifier


def test_standalone_functional_module_loaders_restore_sys_modules() -> None:
    dashboard = read('tests/dashboards/test_dashboard_canonical_repository.py')
    topology = read('tests/inventory/kubernetes/test_topology_canonical_builders.py')

    for source in (dashboard, topology):
        assert 'monkeypatch.setitem(sys.modules' in source
        assert 'sys.modules.setdefault' not in source

    assert "sys.modules['app.common.inventory_generation'] =" not in dashboard
    assert "sys.modules['flask'] =" not in topology
    assert "sys.modules['app.integrations.kubernetes.resolver'] =" not in topology
