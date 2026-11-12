"""Browser regression for server-backed Notification Center Rows selection."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_notification_center_rows_selection_survives_poll_and_keeps_filters(
    configured_page: Page,
    kaori_authenticated_base_url: str,
) -> None:
    page = configured_page
    response = page.goto(f'{kaori_authenticated_base_url}/auth/login', wait_until='domcontentloaded')
    assert response is not None and response.ok

    page.locator('input[name="username"], input[type="email"]').first.fill('browser-admin')
    page.locator('input[name="password"], input[type="password"]').first.fill('ui-test-input')
    page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first.click()
    expect(page).not_to_have_url(re.compile(r'/auth/login(?:[/?#]|$)'))

    response = page.goto(
        f'{kaori_authenticated_base_url}/notifications/?view=notifications&search=artifact&status=all',
        wait_until='domcontentloaded',
    )
    assert response is not None and response.ok

    rows = page.get_by_role('combobox', name='Rows Per Page')
    expect(rows).to_have_value('5')

    for size in ('10', '25', '50'):
        rows.select_option(size)
        expect(page).to_have_url(re.compile(rf'[?&]per_page={size}(?:&|$)'))
        expect(rows).to_have_value(size)
        assert 'search=artifact' in page.url
        assert 'page=1' in page.url

    with page.expect_response(
        lambda result: '/notifications/' in result.url
        and 'per_page=50' in result.url
        and result.status == 200
    ):
        page.locator('body').dispatch_event('kaori:notifications-changed')
    expect(rows).to_have_value('50')

    page.reload(wait_until='domcontentloaded')
    expect(rows).to_have_value('50')
