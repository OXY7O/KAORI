from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_developer_check_routes_ui_tests_and_retains_browser_evidence() -> None:
    workflow = _read('.github/workflows/developer-check.yml')
    planner = _read('scripts/resolve_developer_check_plan.py')

    assert "if path.startswith('tests/ui/'):" in planner
    assert 'frontend = True' in planner
    assert 'tmp/ci-artifacts/test-output/ui-browser' in workflow
    assert 'Upload Browser Diagnostics' in workflow


def test_runtime_state_browser_harness_is_deterministic_and_responsive() -> None:
    conftest = _read('tests/ui/conftest.py')
    runtime_test = ROOT / 'tests/ui/test_runtime_state_responsiveness.py'

    assert 'AuthenticationDatabaseReadiness' in conftest
    assert 'make_server' in conftest
    assert 'kaori_unready_base_url' in conftest
    assert runtime_test.is_file()

    content = runtime_test.read_text(encoding='utf-8')
    assert 'setup_required' in content
    assert 'database_unavailable' in content
    assert 'Database Setup Required' in content
    assert 'scrollWidth' in content
    assert 'clientWidth' in content
    assert 'tracing.start' in content
    assert 'tracing.stop' in content
    assert 'page.screenshot' in content
