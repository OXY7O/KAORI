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
    assert 'expect(page)' in smoke_text
    assert 'page.screenshot' in visual_text
    assert 'KAORI_UPDATE_VISUAL_BASELINES' in visual_text
