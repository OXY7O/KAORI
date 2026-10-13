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
    # Focused pytest now uses the canonical isolated PostgreSQL/Redis Compose
    # test service; browser assets still must be built before that step.
    focused = workflow.index('docker compose --file .github/ci/compose.yml run --rm --no-deps ci')
    assert 'docker compose --file .github/ci/compose.yml up --detach --wait postgres redis' in workflow
    assert 'docker compose --file .github/ci/compose.yml down --volumes --remove-orphans' in workflow
    assert 'COMPOSE_PROJECT_NAME=' in workflow

    assert dependencies < assets < focused, (
        'Developer Check must prepare frontend assets before running routed browser tests.'
    )
