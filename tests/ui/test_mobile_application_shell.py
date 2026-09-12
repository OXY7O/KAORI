from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'
MOBILE_VIEWPORTS = (
    ('mobile', 390, 844),
    ('small-mobile', 360, 800),
)


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
    page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first.click()
    page.wait_for_load_state('networkidle')
    assert '/auth/login' not in page.url


@pytest.mark.parametrize(('viewport_name', 'width', 'height'), MOBILE_VIEWPORTS)
def test_mobile_application_shell_is_full_width_and_drawer_driven(
    page: Page,
    kaori_authenticated_base_url: str,
    viewport_name: str,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({'width': width, 'height': height})
    _login(page, kaori_authenticated_base_url)

    mobile_trigger = page.locator('[data-mobile-navigation-trigger]')
    desktop_toggle = page.locator('[data-desktop-navigation-toggle]')
    drawer = page.locator('[data-mobile-navigation-drawer]')
    backdrop = page.locator('[data-mobile-navigation-backdrop]')

    expect(mobile_trigger).to_be_visible()
    expect(desktop_toggle).to_be_hidden()
    assert drawer.evaluate('(el) => el.getBoundingClientRect().right <= 0')
    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')

    mobile_trigger.click()
    expect(backdrop).to_be_visible()
    assert drawer.evaluate('(el) => el.getBoundingClientRect().left >= 0')
    expect(drawer.get_by_role('button', name='Close navigation')).to_be_visible()

    drawer.get_by_role('button', name='Close navigation').click()
    expect(backdrop).to_be_hidden()
    assert drawer.evaluate('(el) => el.getBoundingClientRect().right <= 0')

    mobile_trigger.click()
    welcome = drawer.get_by_role('link', name='Welcome').first
    expect(welcome).to_be_visible()
    welcome.click()
    page.wait_for_load_state('networkidle')
    expect(backdrop).to_be_hidden()
    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')

    search = page.get_by_role('button', name='Open global search').first
    user_menu = page.get_by_role('button', name='Open user menu')
    expect(search).to_be_visible()
    expect(user_menu).to_be_visible()

    user_menu.click()
    mobile_theme = page.locator('[data-mobile-theme-toggle]')
    expect(mobile_theme).to_be_visible()
    before_class = page.locator('html').get_attribute('class') or ''
    before_theme = page.locator('html').get_attribute('data-theme') or ''
    mobile_theme.click()
    after_class = page.locator('html').get_attribute('class') or ''
    after_theme = page.locator('html').get_attribute('data-theme') or ''
    assert (before_class, before_theme) != (after_class, after_theme), viewport_name
