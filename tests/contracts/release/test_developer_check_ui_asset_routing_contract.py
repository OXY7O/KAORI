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
    focused = workflow.index("printf '⏳ Focused Tests")

    # Real browser tests use canonical isolated PostgreSQL/Redis services.
    assert 'docker compose --file .github/ci/compose.yml up --detach --wait postgres redis' in workflow
    assert 'docker compose --file .github/ci/compose.yml down --volumes --remove-orphans' in workflow
    assert 'COMPOSE_PROJECT_NAME=' in workflow
    test_service = workflow.index('docker compose --file .github/ci/compose.yml run --rm --no-deps ci')
    pytest_invocation = workflow.index('bash -lc "pytest -q --tb=short $paths"')
    assert dependencies < assets < focused < test_service < pytest_invocation, (
        'Developer Check must prepare frontend assets before running routed browser tests.'
    )
