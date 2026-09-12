from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'


@contextmanager
def _browser_evidence(page: Page, scenario: str, viewport_name: str) -> Iterator[None]:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    trace_path = EVIDENCE_ROOT / f'{scenario}-{viewport_name}-trace.zip'
    screenshot_path = EVIDENCE_ROOT / f'{scenario}-{viewport_name}.png'

    page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    try:
        yield
    finally:
        page.screenshot(path=str(screenshot_path), full_page=True, animations='disabled')
        page.context.tracing.stop(path=str(trace_path))


def _login(page: Page, kaori_authenticated_base_url: str) -> None:
    response = page.goto(f'{kaori_authenticated_base_url}/auth/login', wait_until='networkidle')
    assert response is not None
    assert response.ok

    username_field = page.locator('input[name="username"], input[type="email"]').first
    password_field = page.locator('input[name="password"], input[type="password"]').first
    expect(username_field).to_be_visible()
    expect(password_field).to_be_visible()
    username_field.fill(TEST_USERNAME)
    password_field.fill(TEST_PASSWORD)

    submit = page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first
    expect(submit).to_be_visible()
    submit.click()
    page.wait_for_load_state('networkidle')
    assert '/auth/login' not in page.url


def test_user_menu_is_accessible_disclosure_and_escape_restores_focus(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """User menu exposes disclosure state and returns focus after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'user-menu-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = page.get_by_role('button', name='Open user menu')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'user-menu')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.click()
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        menu = page.locator('#user-menu')
        expect(menu).to_be_visible()

        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()
