"""Keep heavy Developer Check workloads sequential on shared self-hosted runners."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_python_typecheck_and_focused_database_suite_cannot_overlap() -> None:
    workflow = yaml.safe_load((ROOT / '.github/workflows/developer-check.yml').read_text(encoding='utf-8'))
    jobs = workflow['jobs']
    python = jobs['python-check']
    focused = jobs['validation-check']
    aggregate = jobs['developer-check']

    assert python['runs-on'] == ['self-hosted', 'linux', 'x64', 'kaori-ci']
    assert focused['runs-on'] == ['self-hosted', 'linux', 'x64', 'kaori-ci']
    assert 'python-check' in focused['needs']
    assert {'python-check', 'validation-check'} <= set(aggregate['needs'])

    condition = focused['if']
    # No implicit success() suppression: frontend-only changes still run
    # when the Python lane legitimately has no paths to validate.
    assert '!cancelled()' in condition
    assert "needs.python-check.result == 'success'" in condition
    assert "needs.python-check.result == 'skipped'" in condition
    assert "needs.route.result == 'success'" in condition
    assert "needs.toolchain.result == 'success'" in condition
    assert "needs.route.outputs.test_paths != ''" in condition
    assert "needs.route.outputs.frontend == 'true'" in condition
    assert "needs.route.outputs.templates == 'true'" in condition
    assert "needs.route.outputs.contracts == 'true'" in condition
