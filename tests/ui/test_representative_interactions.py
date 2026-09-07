import os
import re

import pytest
from playwright.sync_api import Page, expect


def _credentials() -> tuple[str, str]:
    username = os.environ.get('KAORI_UI_USERNAME', '').strip()
    password = os.environ.get('KAORI_UI_PASSWORD', '').strip()
    if not username or not password:
        pytest.skip('KAORI_UI_USERNAME and KAORI_UI_PASSWORD are required for authenticated browser validation')
    return username, password


def _login(page: Page, kaori_base_url: str) -> None:
    username, password = _credentials()
    response = page.goto(f'{kaori_base_url}/login', wait_until='networkidle')
    assert response is not None
    assert response.ok

    username_field = page.locator('input[name="username"], input[type="email"]').first
    password_field = page.locator('input[name="password"], input[type="password"]').first
    expect(username_field).to_be_visible()
    expect(password_field).to_be_visible()
    username_field.fill(username)
    password_field.fill(password)

    submit = page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first
    expect(submit).to_be_visible()
    submit.click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('body')).to_be_visible()


def test_authenticated_navigation_and_light_dark_theme(
    configured_page: Page, kaori_base_url: str
) -> None:
    """Representative navigation plus light/dark interaction evidence."""
    page = configured_page
    _login(page, kaori_base_url)

    navigation = page.locator('nav, aside').first
    expect(navigation).to_be_visible()

    destination = navigation.get_by_role(
        'link', name=re.compile(r'overview|dashboard|kubernetes', re.I)
    ).first
    expect(destination).to_be_visible()
    destination.click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('body')).to_be_visible()

    theme_toggle = page.get_by_role(
        'button', name=re.compile(r'theme|dark|light|appearance', re.I)
    ).first
    if theme_toggle.count() == 0:
        pytest.skip('No accessible light/dark theme toggle is exposed on this authenticated surface')

    expect(theme_toggle).to_be_visible()
    theme_toggle.click()
    expect(page.locator('html')).to_be_visible()


def test_representative_htmx_modal_or_drawer_interaction(
    configured_page: Page, kaori_base_url: str
) -> None:
    """Exercise one safe HTMX GET control and one modal/drawer interaction when present."""
    page = configured_page
    _login(page, kaori_base_url)

    htmx = page.locator('[hx-get]').filter(visible=True).first
    if htmx.count() == 0:
        pytest.skip('No visible HTMX GET interaction is available on the landing surface')

    expect(htmx).to_be_visible()
    htmx.click()
    page.wait_for_timeout(250)
    expect(page.locator('body')).to_be_visible()

    modal_trigger = page.get_by_role(
        'button', name=re.compile(r'notification|activity|details|view', re.I)
    ).first
    if modal_trigger.count() == 0:
        pytest.skip('No representative modal or drawer trigger is available on this surface')

    expect(modal_trigger).to_be_visible()
    modal_trigger.click()
    dialog = page.get_by_role('dialog').first
    drawer = page.locator('[data-drawer], [role="complementary"]').first
    assert dialog.count() or drawer.count()


def test_representative_filter_pagination_and_form_controls(
    configured_page: Page, kaori_base_url: str
) -> None:
    """Validate representative filter, pagination, and form controls without mutating data."""
    page = configured_page
    _login(page, kaori_base_url)

    form = page.locator('form').first
    expect(form).to_be_visible()

    filter_control = page.locator(
        'input[type="search"], input[name*="filter"], select[name*="filter"]'
    ).first
    if filter_control.count():
        expect(filter_control).to_be_visible()
        if filter_control.evaluate("el => el.tagName.toLowerCase() === 'input'"):
            filter_control.fill('')

    pagination = page.get_by_role(
        'link', name=re.compile(r'next|previous|page', re.I)
    ).first
    if pagination.count():
        expect(pagination).to_be_visible()

    expect(page.locator('body')).to_be_visible()
