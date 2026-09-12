from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'
ADAPTIVE_VIEWPORTS = {'tablet', 'mobile', 'small-mobile'}


def _login(page: Page, base_url: str) -> None:
    response = page.goto(f'{base_url}/auth/login', wait_until='networkidle')
    assert response is not None
    assert response.ok

    username = page.locator('input[name="username"], input[type="email"]').first
    password = page.locator('input[name="password"], input[type="password"]').first
    expect(username).to_be_visible()
    expect(password).to_be_visible()
    username.fill(TEST_USERNAME)
    password.fill(TEST_PASSWORD)

    submit = page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first
    expect(submit).to_be_visible()
    submit.click()
    page.wait_for_load_state('networkidle')
    assert '/auth/login' not in page.url


def _assert_no_document_overflow(page: Page) -> None:
    dimensions = page.evaluate(
        '() => ({ scrollWidth: document.documentElement.scrollWidth, '
        'clientWidth: document.documentElement.clientWidth })'
    )
    assert dimensions['scrollWidth'] <= dimensions['clientWidth']


def _capture(page: Page, scenario: str, viewport_name: str) -> None:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE_ROOT / f'{scenario}-{viewport_name}.png'),
        full_page=True,
        animations='disabled',
    )


def test_authenticated_shell_adapts_across_canonical_viewports(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    page = configured_page
    viewport_name, _ = kaori_viewport
    _login(page, kaori_authenticated_base_url)
    _assert_no_document_overflow(page)

    sidebar = page.locator('[data-mobile-navigation]')
    mobile_trigger = page.locator('[data-mobile-menu-trigger]')
    desktop_toggle = page.get_by_role(
        'button', name=re.compile(r'collapse navigation|expand navigation', re.I)
    )

    if viewport_name in ADAPTIVE_VIEWPORTS:
        expect(mobile_trigger).to_be_visible()
        expect(desktop_toggle).to_be_hidden()
        expect(page.locator('[data-mobile-page-intro]')).to_be_visible()
        expect(page.locator('.kaori-hero-shell')).to_be_hidden()

        resting_box = sidebar.bounding_box()
        assert resting_box is not None
        assert resting_box['x'] + resting_box['width'] <= 1

        mobile_trigger.click()
        expect(page.locator('[data-mobile-navigation-backdrop]')).to_be_visible()
        expect(page.locator('[data-mobile-navigation-close]')).to_be_visible()
        open_box = sidebar.bounding_box()
        assert open_box is not None
        assert open_box['x'] >= 0
        expect(sidebar.get_by_role('link', name='Welcome')).to_be_visible()

        page.locator('[data-mobile-navigation-close]').click()
        page.wait_for_timeout(250)
        closed_box = sidebar.bounding_box()
        assert closed_box is not None
        assert closed_box['x'] + closed_box['width'] <= 1

        expect(page.get_by_role('button', name='Open global search')).to_be_visible()
        expect(page.get_by_role('button', name='Open notification deck')).to_be_visible()
        expect(page.get_by_role('button', name='Toggle theme')).to_be_visible()
        expect(page.get_by_role('button', name='Open user menu')).to_be_visible()
        _assert_no_document_overflow(page)
    else:
        expect(desktop_toggle).to_be_visible()
        expect(mobile_trigger).to_be_hidden()
        expect(page.locator('.kaori-hero-shell')).to_be_visible()
        desktop_box = sidebar.bounding_box()
        assert desktop_box is not None
        assert desktop_box['x'] >= 0

    _capture(page, 'authenticated-responsive-shell', viewport_name)


def test_mobile_navigation_closes_after_destination_selection(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    page = configured_page
    viewport_name, _ = kaori_viewport
    if viewport_name not in ADAPTIVE_VIEWPORTS:
        return

    _login(page, kaori_authenticated_base_url)
    page.locator('[data-mobile-menu-trigger]').click()
    sidebar = page.locator('[data-mobile-navigation]')
    destination = sidebar.get_by_role('link', name='Welcome')
    expect(destination).to_be_visible()
    destination.click()
    page.wait_for_load_state('networkidle')

    resting_box = page.locator('[data-mobile-navigation]').bounding_box()
    assert resting_box is not None
    assert resting_box['x'] + resting_box['width'] <= 1
    _assert_no_document_overflow(page)
