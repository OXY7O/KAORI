from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

CANONICAL_VIEWPORTS = {
    'large-desktop': (1440, 900),
    'laptop': (1280, 800),
    'compact-laptop': (1024, 768),
    'tablet': (768, 1024),
    'mobile': (390, 844),
    'small-mobile': (360, 800),
}


def test_playwright_toolchain_is_pinned_and_browser_is_baked_into_ci_image() -> None:
    requirements = (ROOT / 'requirements' / 'dev.txt').read_text()
    dockerfile = (ROOT / '.github' / 'ci' / 'Dockerfile').read_text()

    assert 'playwright==1.62.0' in requirements
    assert 'pytest-playwright==0.9.0' in requirements
    assert 'python -m playwright install --with-deps chromium' in dockerfile


def test_ui_harness_declares_canonical_viewport_matrix() -> None:
    conftest = (ROOT / 'tests' / 'ui' / 'conftest.py').read_text()

    for name, (width, height) in CANONICAL_VIEWPORTS.items():
        assert f"'{name}': ({width}, {height})" in conftest


def test_ui_harness_has_browser_smoke_and_visual_regression_authority() -> None:
    smoke = ROOT / 'tests' / 'ui' / 'test_browser_smoke.py'
    visual = ROOT / 'tests' / 'ui' / 'test_visual_regression.py'

    assert smoke.is_file()
    assert visual.is_file()

    smoke_text = smoke.read_text()
    visual_text = visual.read_text()
    assert 'page.goto' in smoke_text
    assert 'expect(' in smoke_text
    assert '.to_be_visible()' in smoke_text
    assert 'page.screenshot' in visual_text
    assert 'KAORI_UPDATE_VISUAL_BASELINES' in visual_text


def test_visual_baseline_capture_is_governed_and_reviewable() -> None:
    workflow = ROOT / '.github' / 'workflows' / 'ui-visual-baseline-capture.yml'

    assert workflow.is_file()
    workflow_text = workflow.read_text()
    assert 'workflow_dispatch:' in workflow_text
    assert 'KAORI_UI_BASE_URL' in workflow_text
    assert 'KAORI_UPDATE_VISUAL_BASELINES: "1"' in workflow_text
    assert 'pytest -q tests/ui/test_visual_regression.py' in workflow_text
    assert 'actions/upload-artifact@' in workflow_text
    assert 'tests/ui/baselines' in workflow_text
    assert 'tests/ui/artifacts' in workflow_text


def test_representative_browser_interaction_families_have_executable_authority() -> None:
    interactions = ROOT / 'tests' / 'ui' / 'test_representative_interactions.py'

    assert interactions.is_file()
    source = interactions.read_text()
    assert '/auth/login' in source
    assert 'KAORI_UI_USERNAME' not in source
    assert 'KAORI_UI_PASSWORD' not in source
    assert 'pytest.skip(' not in source
    assert 'page.goto' in source
    assert 'page.get_by_role' in source
    assert 'expect(' in source
    assert 'navigation' in source.lower()
    assert 'htmx' in source.lower()
    assert 'modal' in source.lower() or 'drawer' in source.lower()
    assert 'pagination' in source.lower() or 'filter' in source.lower()
    assert 'form' in source.lower()
    assert 'dark' in source.lower() and 'light' in source.lower()
