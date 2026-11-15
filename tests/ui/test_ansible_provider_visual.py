"""Ansible provider desktop/mobile visual evidence using existing KAORI Playwright fixtures."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
BASE_PATH = '/integrations/orchestration/ansible/'


@pytest.mark.parametrize(
    ('viewport_name', 'width', 'height'),
    [('large-desktop', 1440, 900), ('mobile', 390, 844)],
)
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_ansible_provider_reviewable_visual_surfaces(
    page: Page,
    kaori_authenticated_base_url: str,
    viewport_name: str,
    width: int,
    height: int,
    theme: str,
) -> None:
    page.set_viewport_size({'width': width, 'height': height})
    response = page.goto(f'{kaori_authenticated_base_url}/auth/login', wait_until='domcontentloaded')
    assert response is not None and response.ok
    username = page.locator('input[name="username"], input[type="email"]').first
    password = page.locator('input[name="password"], input[type="password"]').first
    expect(username).to_be_visible()
    expect(password).to_be_visible()
    username.fill('browser-admin')
    password.fill('ui-test-input')
    page.get_by_role('button', name=re.compile(r'log in|login|sign in', re.I)).first.click()
    expect(page).not_to_have_url(re.compile(r'/auth/login(?:[/?#]|$)'))

    css = page.request.get(f'{kaori_authenticated_base_url}/static/css/output.css')
    assert css.ok, 'Canonical KAORI Tailwind CSS must be built before visual QA'

    overview = page.goto(f'{kaori_authenticated_base_url}{BASE_PATH}', wait_until='domcontentloaded')
    assert overview is not None and overview.ok
    if theme == 'dark':
        page.get_by_role('button', name='Toggle theme').click()
    expect(page.get_by_role('heading', name='Ansible Infrastructure Automation')).to_be_visible()
    expect(page.get_by_role('heading', name='Connection Registry')).to_be_visible()
    expect(page.get_by_role('link', name='Add Connection')).to_be_visible()
    candidates = page.locator('[data-kaori-ansible-registry] a[href*="/instances/"]')
    detail_href = next(
        (
            href
            for link in candidates.all()
            if (href := link.get_attribute('href')) and re.search(r'/instances/\d+$', href)
        ),
        None,
    )
    assert detail_href is not None, 'Expected the registered CI Ansible instance in the registry'
    _assert_no_document_overflow(page)

    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE_ROOT / f'ansible-overview-{theme}-{viewport_name}.png'),
        full_page=True,
        animations='disabled',
    )

    register = page.goto(
        f'{kaori_authenticated_base_url}{BASE_PATH}instances/new', wait_until='domcontentloaded'
    )
    assert register is not None and register.ok
    expect(page.get_by_role('heading', name='Register Ansible Connection')).to_be_visible()
    expect(page.locator('form[action*="instances/new"] input[name="csrf_token"]')).to_have_count(1)
    expect(page.locator('input[name="ssh_private_key"]')).to_have_count(0)
    expect(page.get_by_role('button', name='Register Connection')).to_be_visible()
    _assert_no_document_overflow(page)
    page.screenshot(
        path=str(EVIDENCE_ROOT / f'ansible-register-{theme}-{viewport_name}.png'),
        full_page=True,
        animations='disabled',
    )

    detail = page.goto(f'{kaori_authenticated_base_url}{detail_href}', wait_until='domcontentloaded')
    assert detail is not None and detail.ok
    expect(page.get_by_role('heading', name='Read-only Execution Evidence')).to_be_visible()
    expect(page.get_by_role('button', name='Run Local Read-only Test')).to_be_visible()
    expect(page.get_by_role('heading', name='External Host Validation')).to_be_visible()
    _assert_no_document_overflow(page)
    page.screenshot(
        path=str(EVIDENCE_ROOT / f'ansible-detail-{theme}-{viewport_name}.png'),
        full_page=True,
        animations='disabled',
    )


def _assert_no_document_overflow(page: Page) -> None:
    size = page.evaluate(
        '() => ({ scrollWidth: document.documentElement.scrollWidth, '
        'clientWidth: document.documentElement.clientWidth })'
    )
    assert size['scrollWidth'] <= size['clientWidth'] + 1, f'Horizontal overflow: {size}'
