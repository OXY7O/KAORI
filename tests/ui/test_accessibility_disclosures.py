from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Locator, Page, expect

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


def _visible_button(page: Page, accessible_name: str) -> Locator:
    return page.locator(f'button[aria-label="{accessible_name}"]:visible').first


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
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        menu = page.locator('#user-menu')
        expect(menu).to_be_visible()

        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_quick_actions_disclosure_restores_focus_after_escape(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Quick Actions exposes ownership and restores its visible trigger after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'quick-actions-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = _visible_button(page, 'Open quick actions')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'quick-actions-menu')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        menu = page.locator('#quick-actions-menu')
        expect(menu).to_be_visible()
        menu.locator('a, button').first.focus()

        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_global_search_dialog_restores_trigger_focus_after_escape(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Global Search owns its dialog, focuses search, and restores its trigger after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'global-search-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = _visible_button(page, 'Open global search')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'global-search')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        dialog = page.get_by_role('dialog', name='Search KAORI')
        search_input = page.get_by_role('combobox', name='Search KAORI resources and pages')
        expect(dialog).to_be_visible()
        expect(search_input).to_be_focused()

        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_about_dialog_focus_is_contained_and_returns_to_user_menu_trigger(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """About dialog receives/traps focus and returns to the logical disclosure trigger."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'about-dialog-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        user_trigger = page.get_by_role('button', name='Open user menu')
        user_trigger.press('Enter')
        about_trigger = page.get_by_role('button', name='About')
        expect(about_trigger).to_be_visible()
        about_trigger.press('Enter')

        dialog = page.get_by_role('dialog', name='About KAORI')
        expect(dialog).to_be_visible()
        expect(dialog).to_be_focused()

        close_button = dialog.get_by_role('button', name='Close About KAORI')
        close_button.focus()
        page.keyboard.press('Shift+Tab')
        assert dialog.evaluate('(element) => element.contains(document.activeElement)') is True

        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(user_trigger).to_be_focused()
