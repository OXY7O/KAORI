from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'


def test_functional_gate_prepares_exact_css_before_browser_inclusive_pytest() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    run_tests = source.split('run_tests() {', 1)[1].split('\n}\n\nrun_frontend()', 1)[0]

    install = 'npm ci --no-audit --no-fund'
    build_css = 'npm run build-css'
    pytest_start = "run_pytest_capture \\\n        'Functional Tests'"

    assert install in run_tests
    assert build_css in run_tests
    assert pytest_start in run_tests
    assert run_tests.index(install) < run_tests.index(pytest_start)
    assert run_tests.index(build_css) < run_tests.index(pytest_start)
