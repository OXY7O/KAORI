from pathlib import Path


WORKFLOW = Path('.github/workflows/developer-check.yml')


def test_ui_browser_changes_prepare_frontend_assets_before_tests() -> None:
    workflow = WORKFLOW.read_text()

    ui_route = "tests/ui/*)\n                frontend=true\n                selected_tests[tests/ui]=1"

    assert ui_route in workflow, (
        'Developer Check must route tests/ui changes through frontend asset preparation '
        'before running browser tests.'
    )
