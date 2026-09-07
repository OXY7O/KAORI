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
    expect(page.locator('body')).to_be_visible()
    assert '/auth/login' not in page.url


def test_authenticated_navigation_and_light_dark_theme(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Exercise authenticated shell navigation and the shared light/dark control."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'authenticated-navigation-theme', viewport_name):
        _login(page, kaori_authenticated_base_url)

        navigation = page.locator('nav, aside').first
        expect(navigation).to_be_visible()

        destination = navigation.get_by_role('link', name=re.compile(r'welcome', re.I)).first
        expect(destination).to_be_visible()
        destination.click()
        page.wait_for_load_state('networkidle')
        expect(page.locator('body')).to_be_visible()

        theme_toggle = page.get_by_role('button', name=re.compile(r'theme|dark|light|appearance', re.I)).first
        expect(theme_toggle).to_be_visible()
        before_class = page.locator('html').get_attribute('class') or ''
        before_theme = page.locator('html').get_attribute('data-theme') or ''
        theme_toggle.click()
        after_class = page.locator('html').get_attribute('class') or ''
        after_theme = page.locator('html').get_attribute('data-theme') or ''
        assert (before_class, before_theme) != (after_class, after_theme)


def test_representative_htmx_modal_or_drawer_interaction(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Exercise a safe shared-shell HTMX interaction and modal/drawer presentation."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'authenticated-htmx-overlay', viewport_name):
        _login(page, kaori_authenticated_base_url)

        htmx = page.locator('[hx-get]').filter(visible=True).first
        assert htmx.count() > 0
        expect(htmx).to_be_visible()
        htmx.click()
        page.wait_for_timeout(250)
        expect(page.locator('body')).to_be_visible()

        modal_trigger = page.get_by_role('button', name=re.compile(r'notification|activity|details|view', re.I)).first
        expect(modal_trigger).to_be_visible()
        modal_trigger.click()
        dialog = page.get_by_role('dialog').first
        drawer = page.locator('[data-drawer], [role="complementary"]').first
        assert dialog.count() or drawer.count()


def test_representative_filter_pagination_and_form_controls(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Validate representative filter, pagination, and form controls without mutating data."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'authenticated-filter-form', viewport_name):
        _login(page, kaori_authenticated_base_url)

        form = page.locator('form').first
        expect(form).to_be_visible()

        filter_control = page.locator('input[type="search"], input[name*="filter"], select[name*="filter"]').first
        pagination = page.get_by_role('link', name=re.compile(r'next|previous|page', re.I)).first
        assert filter_control.count() or pagination.count()

        if filter_control.count():
            expect(filter_control).to_be_visible()
            if filter_control.evaluate("el => el.tagName.toLowerCase() === 'input'"):
                filter_control.fill('')

        if pagination.count():
            expect(pagination).to_be_visible()

        expect(page.locator('body')).to_be_visible()
