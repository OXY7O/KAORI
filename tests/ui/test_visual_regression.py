import hashlib
import os
from pathlib import Path

from playwright.sync_api import Page

BASELINE_ROOT = Path(__file__).with_name('baselines')


def _baseline_path(viewport_name: str) -> Path:
    return BASELINE_ROOT / f'login-{viewport_name}.sha256'


def test_login_visual_baseline(configured_page: Page, kaori_base_url: str, kaori_viewport: tuple[str, tuple[int, int]]) -> None:
    page = configured_page
    viewport_name, _ = kaori_viewport
    response = page.goto(f'{kaori_base_url}/login', wait_until='networkidle')

    assert response is not None
    assert response.ok

    screenshot = page.screenshot(full_page=True, animations='disabled')
    digest = hashlib.sha256(screenshot).hexdigest()
    baseline = _baseline_path(viewport_name)

    if os.environ.get('KAORI_UPDATE_VISUAL_BASELINES') == '1':
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(f'{digest}\n')
        return

    assert baseline.is_file(), f'missing reviewed visual baseline: {baseline}'
    assert baseline.read_text().strip() == digest
