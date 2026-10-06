from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_AUTH_INPUT = 'ui-test-input'
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
    password.fill(TEST_AUTH_INPUT)

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
    desktop_toggle = page.get_by_role('button', name=re.compile(r'collapse navigation|expand navigation', re.I))
    welcome_hero = page.locator('section.kaori-hero-shell').first
    expect(welcome_hero).to_be_visible()
    expect(page.get_by_role('heading', name='Welcome to KAORI')).to_be_visible()

    if viewport_name in {'mobile', 'small-mobile'}:
        hero_box = welcome_hero.bounding_box()
        assert hero_box is not None
        assert page.viewport_size is not None
        assert hero_box['height'] < page.viewport_size['height'] * 0.8
        expect(welcome_hero.locator('[data-kaori-hero-leading-icon]')).to_be_hidden()
        metadata_items = welcome_hero.locator('[data-kaori-hero-metadata-item]')
        assert metadata_items.count() >= 2
        expect(metadata_items.nth(0)).to_be_visible()
        expect(metadata_items.nth(1)).to_be_hidden()
        context_metrics = welcome_hero.locator('[data-kaori-hero-context-metric]')
        assert context_metrics.count() >= 2
        expect(context_metrics.nth(0)).to_be_visible()
        expect(context_metrics.nth(1)).to_be_hidden()
        _assert_no_document_overflow(page)

    if viewport_name in ADAPTIVE_VIEWPORTS:
        expect(mobile_trigger).to_be_visible()
        expect(desktop_toggle).to_be_hidden()

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
    page.evaluate("localStorage.setItem('kaori.sidebarExpanded', 'false')")
    page.reload(wait_until='networkidle')

    mobile_trigger = page.locator('[data-mobile-menu-trigger]')
    sidebar = page.locator('[data-mobile-navigation]')
    mobile_trigger.click()

    open_box = sidebar.bounding_box()
    assert open_box is not None
    assert open_box['width'] > 200
    expect(sidebar.get_by_role('link', name='Welcome')).to_be_visible()

    parent_menu = sidebar.locator('summary[aria-label]').first
    expect(parent_menu).to_be_visible()
    parent_menu.click()
    assert page.evaluate("localStorage.getItem('kaori.sidebarExpanded')") == 'false'

    page.locator('[data-mobile-navigation-close]').click()
    expect(page.locator('[data-mobile-navigation-backdrop]')).to_be_hidden()
    closed_box = sidebar.bounding_box()
    assert closed_box is not None
    assert closed_box['width'] > 200
    assert abs(closed_box['width'] - open_box['width']) < 1
    assert page.evaluate("localStorage.getItem('kaori.sidebarExpanded')") == 'false'

    mobile_trigger.click()
    destination = sidebar.get_by_role('link', name='Welcome')
    expect(destination).to_be_visible()
    destination.click()
    page.wait_for_load_state('networkidle')

    resting_sidebar = page.locator('[data-mobile-navigation]')
    resting_box = resting_sidebar.bounding_box()
    assert resting_box is not None
    assert resting_box['x'] + resting_box['width'] <= 1
    assert resting_box['width'] > 200
    assert page.evaluate("localStorage.getItem('kaori.sidebarExpanded')") == 'false'

    page.locator('[data-mobile-menu-trigger]').click()
    reopened_box = page.locator('[data-mobile-navigation]').bounding_box()
    assert reopened_box is not None
    assert reopened_box['width'] > 200
    assert abs(reopened_box['width'] - resting_box['width']) < 1
    expect(page.locator('[data-mobile-navigation-close]')).to_be_focused()
    _assert_no_document_overflow(page)


def test_authenticated_shell_scroll_targets_preserve_top_boundary(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Programmatic/fragment-style scrolling keeps content below the shell-owned top inset."""
    page = configured_page
    viewport_name, _ = kaori_viewport
    _login(page, kaori_authenticated_base_url)

    main = page.locator('main[data-kaori-main-scroll]')
    hero = page.locator('section.kaori-hero-shell').first
    expect(main).to_be_visible()
    expect(hero).to_be_visible()

    initial = page.evaluate(
        """() => {
            const main = document.querySelector('main[data-kaori-main-scroll]');
            const wrapper = main.firstElementChild;
            const hero = document.querySelector('section.kaori-hero-shell');
            const mainRect = main.getBoundingClientRect();
            const heroRect = hero.getBoundingClientRect();
            return {
                mainTop: mainRect.top,
                heroTop: heroRect.top,
                contentPaddingTop: Number.parseFloat(getComputedStyle(wrapper).paddingTop),
                scrollPaddingTop: Number.parseFloat(getComputedStyle(main).scrollPaddingTop),
            };
        }"""
    )
    assert initial['contentPaddingTop'] > 0
    assert abs(initial['scrollPaddingTop'] - initial['contentPaddingTop']) < 0.5
    assert initial['heroTop'] >= initial['mainTop'] + initial['contentPaddingTop'] - 1

    page.evaluate(
        """() => {
            const main = document.querySelector('main[data-kaori-main-scroll]');
            const wrapper = main.firstElementChild;
            const spacerBefore = document.createElement('div');
            spacerBefore.style.height = '1200px';
            const target = document.createElement('section');
            target.id = 'shell-scroll-boundary-probe';
            target.textContent = 'Scroll boundary probe';
            target.style.minHeight = '40px';
            const spacerAfter = document.createElement('div');
            spacerAfter.style.height = '1200px';
            wrapper.append(spacerBefore, target, spacerAfter);
            target.scrollIntoView({ block: 'start' });
        }"""
    )

    probe = page.locator('#shell-scroll-boundary-probe')
    expect(probe).to_be_visible()
    aligned = page.evaluate(
        """() => {
            const main = document.querySelector('main[data-kaori-main-scroll]');
            const target = document.querySelector('#shell-scroll-boundary-probe');
            const mainRect = main.getBoundingClientRect();
            const targetRect = target.getBoundingClientRect();
            const wrapper = main.firstElementChild;
            return {
                mainTop: mainRect.top,
                targetTop: targetRect.top,
                contentPaddingTop: Number.parseFloat(getComputedStyle(wrapper).paddingTop),
                scrollPaddingTop: Number.parseFloat(getComputedStyle(main).scrollPaddingTop),
                mainScrollTop: main.scrollTop,
            };
        }"""
    )
    assert aligned['mainScrollTop'] > 0
    assert abs(aligned['scrollPaddingTop'] - aligned['contentPaddingTop']) < 0.5
    assert aligned['targetTop'] >= aligned['mainTop'] + aligned['scrollPaddingTop'] - 1
    _assert_no_document_overflow(page)
    _capture(page, 'authenticated-shell-top-boundary', viewport_name)
