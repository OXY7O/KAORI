import os

import pytest
from playwright.sync_api import Page

CANONICAL_VIEWPORTS = {
    'large-desktop': (1440, 900),
    'laptop': (1280, 800),
    'compact-laptop': (1024, 768),
    'tablet': (768, 1024),
    'mobile': (390, 844),
    'small-mobile': (360, 800),
}


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if 'kaori_viewport' not in metafunc.fixturenames:
        return

    viewports = list(CANONICAL_VIEWPORTS.items())
    metafunc.parametrize('kaori_viewport', viewports, ids=[name for name, _ in viewports])


@pytest.fixture
def kaori_base_url() -> str:
    base_url = os.environ.get('KAORI_UI_BASE_URL', '').strip()
    if not base_url:
        pytest.skip('KAORI_UI_BASE_URL is required for browser-based UI validation')
    return base_url.rstrip('/')


@pytest.fixture
def configured_page(page: Page, kaori_viewport: tuple[str, tuple[int, int]]) -> Page:
    _, (width, height) = kaori_viewport
    page.set_viewport_size({'width': width, 'height': height})
    return page
