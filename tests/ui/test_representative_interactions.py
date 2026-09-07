from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'
NOTIFICATION_CENTER_PATH = '/notifications/?view=notifications'


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


def _open_notification_center(page: Page, kaori_authenticated_base_url: str) -> None:
    response = page.goto(
        f'{kaori_authenticated_base_url}{NOTIFICATION_CENTER_PATH}',
        wait_until='networkidle',
    )
    assert response is not None
    assert response.ok
    expect(page.locator('#activity-notification-page')).to_be_visible()


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
    """Exercise Notification Center HTMX refresh and the shared Notification Deck."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'authenticated-htmx-overlay', viewport_name):
        _login(page, kaori_authenticated_base_url)
        _open_notification_center(page, kaori_authenticated_base_url)

        htmx_surface = page.locator('#activity-notification-page[hx-get]')
        expect(htmx_surface).to_be_visible()
        with page.expect_response(
            lambda response: '/notifications/' in response.url
            and response.request.method == 'GET'
            and response.request.headers.get('hx-request') == 'true'
        ):
            page.locator('body').evaluate(
                "el => el.dispatchEvent(new CustomEvent('kaori:notifications-changed', { bubbles: true }))"
            )
        expect(page.locator('#activity-notification-page')).to_be_visible()

        modal_trigger = page.get_by_role('button', name='Open notification deck')
        expect(modal_trigger).to_be_visible()
        modal_trigger.click()
        dialog = page.get_by_role('dialog', name='Notification deck')
        expect(dialog).to_be_visible()
        expect(page.locator('#notification-deck')).to_be_visible()


def test_representative_filter_pagination_and_form_controls(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Validate the Notification Center filter, pagination, and GET-only form controls."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'authenticated-filter-form', viewport_name):
        _login(page, kaori_authenticated_base_url)
        _open_notification_center(page, kaori_authenticated_base_url)

        search_control = page.locator('#notification-center-search')
        filter_form = page.locator('form:has(#notification-center-search)')
        category_filter = page.locator('#notification-center-category')
        rows_control = page.locator('#notification-center-per-page')
        pagination = page.get_by_role('navigation', name='Notification Center pagination')

        expect(filter_form).to_be_visible()
        expect(search_control).to_be_visible()
        expect(category_filter).to_be_visible()
        expect(rows_control).to_be_visible()
        expect(pagination).to_be_visible()
        assert filter_form.get_attribute('hx-get')

        with page.expect_response(
            lambda response: '/notifications/' in response.url
            and 'search=browser' in response.url
            and response.request.method == 'GET'
            and response.request.headers.get('hx-request') == 'true'
        ):
            search_control.fill('browser')
        expect(page.locator('#notification-center-search')).to_be_visible()
        expect(page.get_by_role('navigation', name='Notification Center pagination')).to_be_visible()
