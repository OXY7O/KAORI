from __future__ import annotations

from pathlib import Path

WORKFLOW = Path('.github/workflows/developer-check.yml')
PLANNER = Path('scripts/developer_check_plan.py')


def test_ui_browser_changes_prepare_frontend_assets_before_tests() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    planner = PLANNER.read_text(encoding='utf-8')

    assert "path.startswith('tests/ui/')" in planner
    assert 'plan.frontend = True' in planner
    assert "plan.add_test_path('tests/ui')" in planner

    dependencies = workflow.index("run_toolchain 'Frontend Dependencies'")
    assets = workflow.index("run_toolchain 'Frontend Test Assets'")
    focused = workflow.index("run_toolchain 'Focused Tests'")

    assert dependencies < assets < focused, (
        'Developer Check must prepare frontend assets before running routed browser tests.'
    )
