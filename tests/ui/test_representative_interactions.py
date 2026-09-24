from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, expect

from tests.ui.visual_audit import (
    DETERMINISTIC_VISUAL_SURFACES,
    VisualAuditFinding,
    assert_document_fits_viewport,
    assert_hero_description_contract,
    assert_primary_actions_visible,
    assert_visual_baseline,
    record_visual_audit_finding,
)

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'
NOTIFICATION_CENTER_PATH = '/notifications/?view=notifications'
ADAPTIVE_VIEWPORTS = {'tablet', 'mobile', 'small-mobile'}


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


def _load_persisted_visual_theme(page: Page, visual_theme: str) -> None:
    """Render a deterministic final theme through the application pre-paint bootstrap."""
    assert visual_theme in {'light', 'dark'}
    page.evaluate("(theme) => window.localStorage.setItem('theme', theme)", visual_theme)

    response = page.reload(wait_until='networkidle')
    assert response is not None
    assert response.ok
    expect(page.locator('body')).to_be_visible()
    expect(page.locator('#theme-toggle')).to_be_visible()

    html = page.locator('html')
    class_tokens = (html.get_attribute('class') or '').split()
    assert ('dark' in class_tokens) == (visual_theme == 'dark')
    assert page.evaluate("() => window.localStorage.getItem('theme')") == visual_theme


def _open_notification_center(page: Page, kaori_authenticated_base_url: str) -> None:
    response = page.goto(
        f'{kaori_authenticated_base_url}{NOTIFICATION_CENTER_PATH}',
        wait_until='networkidle',
    )
    assert response is not None
    assert response.ok
    expect(page.locator('#activity-notification-page')).to_be_visible()


def _open_primary_navigation(page: Page, viewport_name: str):
    navigation = page.locator('[data-mobile-navigation]')
    if viewport_name in ADAPTIVE_VIEWPORTS:
        trigger = page.locator('[data-mobile-menu-trigger]')
        expect(trigger).to_be_visible()
        trigger.click()
        expect(page.locator('[data-mobile-navigation-close]')).to_be_visible()
    expect(navigation).to_be_visible()
    return navigation


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

        navigation = _open_primary_navigation(page, viewport_name)
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


def test_hero_description_is_one_untruncated_line_on_non_phone_viewports(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Keep the shared Hero description to one visible line on every canonical non-phone viewport."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    if viewport_name not in {'large-desktop', 'laptop', 'compact-laptop', 'tablet'}:
        return

    with _browser_evidence(page, 'hero-description-single-line', viewport_name):
        _login(page, kaori_authenticated_base_url)

        description = page.locator('.kaori-hero-description').first
        expect(description).to_be_visible()
        metrics = description.evaluate(
            """element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return {
                    clientWidth: element.clientWidth,
                    scrollWidth: element.scrollWidth,
                    height: rect.height,
                    lineHeight: Number.parseFloat(style.lineHeight),
                };
            }"""
        )
        assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1
        assert metrics['height'] <= metrics['lineHeight'] + 1


def test_welcome_visual_qa_light_and_dark(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Capture deterministic Welcome visual evidence in both supported themes."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    _login(page, kaori_authenticated_base_url)

    for visual_theme in ('light', 'dark'):
        with _browser_evidence(page, f'welcome-{visual_theme}', viewport_name):
            _load_persisted_visual_theme(page, visual_theme)

            evidence_name = f'welcome-{visual_theme}-{viewport_name}.png'
            try:
                assert_document_fits_viewport(page)
                assert_hero_description_contract(page, viewport_name)
                assert_primary_actions_visible(page)
                assert_visual_baseline(
                    page,
                    surface='welcome',
                    theme=visual_theme,
                    viewport_name=viewport_name,
                )
            except AssertionError as exc:
                record_visual_audit_finding(
                    VisualAuditFinding(
                        status='Broken',
                        surface='Welcome',
                        viewport=viewport_name,
                        theme=visual_theme,
                        component='Shared visual surface',
                        invariant='Geometry and visual baseline',
                        evidence=str(exc),
                    )
                )
                raise
            else:
                record_visual_audit_finding(
                    VisualAuditFinding(
                        status='PASS',
                        surface='Welcome',
                        viewport=viewport_name,
                        theme=visual_theme,
                        component='Shared visual surface',
                        invariant='Geometry and visual baseline',
                        evidence=evidence_name,
                    )
                )


def test_deterministic_visual_surface_catalog_light_and_dark(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Audit every currently deterministic visual surface across canonical themes and viewports."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    _login(page, kaori_authenticated_base_url)

    for endpoint, (surface_label, path) in DETERMINISTIC_VISUAL_SURFACES.items():
        response = page.goto(f'{kaori_authenticated_base_url}{path}', wait_until='networkidle')
        assert response is not None, endpoint
        assert response.ok, endpoint
        expect(page.locator('body')).to_be_visible()

        html = page.locator('html')
        toggle = page.locator('#theme-toggle')
        expect(toggle).to_be_visible()

        for visual_theme in ('light', 'dark'):
            with _browser_evidence(
                page,
                f'visual-{endpoint.replace(".", "-")}-{visual_theme}',
                viewport_name,
            ):
                is_dark = 'dark' in (html.get_attribute('class') or '').split()
                if (visual_theme == 'dark') != is_dark:
                    toggle.click()

                class_tokens = (html.get_attribute('class') or '').split()
                assert ('dark' in class_tokens) == (visual_theme == 'dark')

                evidence_name = f'visual-{endpoint.replace(".", "-")}-{visual_theme}-{viewport_name}.png'
                try:
                    assert_document_fits_viewport(page)
                    assert_hero_description_contract(page, viewport_name)
                    assert_primary_actions_visible(page)
                except AssertionError as exc:
                    record_visual_audit_finding(
                        VisualAuditFinding(
                            status='Broken',
                            surface=surface_label,
                            viewport=viewport_name,
                            theme=visual_theme,
                            component='Deterministic visual surface',
                            invariant='Shared geometry',
                            evidence=str(exc),
                        )
                    )
                    raise
                else:
                    record_visual_audit_finding(
                        VisualAuditFinding(
                            status='PASS',
                            surface=surface_label,
                            viewport=viewport_name,
                            theme=visual_theme,
                            component='Deterministic visual surface',
                            invariant='Shared geometry',
                            evidence=evidence_name,
                        )
                    )


def test_reduced_motion_keeps_shared_loading_and_overlay_state_without_animation(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Keep shared loading and overlay state visible without non-essential motion."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    if viewport_name != 'laptop':
        return

    page.emulate_media(reduced_motion='reduce')

    with _browser_evidence(page, 'reduced-motion-shared-feedback', viewport_name):
        _login(page, kaori_authenticated_base_url)
        _open_notification_center(page, kaori_authenticated_base_url)

        assert page.evaluate("() => window.matchMedia('(prefers-reduced-motion: reduce)').matches")

        segment = page.locator('#notification-center-loading .kaori-loading-bar-segment')
        expect(segment).to_be_attached()
        segment_motion = segment.evaluate(
            """element => {
                const style = window.getComputedStyle(element);
                return {
                    animationName: style.animationName,
                    transform: style.transform,
                };
            }"""
        )
        assert segment_motion['animationName'] == 'none'
        assert segment_motion['transform'] == 'none'

        trigger = page.get_by_role('button', name='Open notification deck')
        expect(trigger).to_be_visible()
        trigger.click()
        deck = page.locator('#notification-deck')
        expect(deck).to_be_visible()
        deck_motion = deck.evaluate(
            """element => {
                const style = window.getComputedStyle(element);
                return {
                    transitionDuration: style.transitionDuration,
                    transform: style.transform,
                };
            }"""
        )
        assert deck_motion['transitionDuration'] == '0s'
        assert deck_motion['transform'] == 'none'


def test_notification_deck_escape_restores_trigger_focus(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Closing the Notification Deck with Escape returns focus to its trigger."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'notification-deck-focus-return', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = page.get_by_role('button', name='Open notification deck')
        expect(trigger).to_be_visible()
        trigger.focus()
        trigger.click()

        dialog = page.get_by_role('dialog', name='Notification deck')
        expect(dialog).to_be_visible()

        if viewport_name in {'mobile', 'small-mobile'}:
            deck = page.locator('#notification-deck')
            deck_box = deck.bounding_box()
            assert deck_box is not None
            assert page.viewport_size is not None
            assert deck_box['width'] <= page.viewport_size['width']
            assert deck_box['width'] >= page.viewport_size['width'] - 2

            tabs = dialog.locator('[data-notification-deck-tabs]')
            expect(tabs).to_be_visible()
            for label in ('Active Work', 'Inbox', 'Notifications'):
                expect(tabs.get_by_role('tab', name=re.compile(label, re.I))).to_be_visible()

            footer = dialog.locator('[data-notification-deck-footer]')
            expect(footer).to_be_visible()
            footer_box = footer.bounding_box()
            action = footer.get_by_role('link', name='View All')
            action_box = action.bounding_box()
            assert footer_box is not None
            assert action_box is not None
            assert action_box['width'] >= footer_box['width'] * 0.8

            dimensions = page.evaluate(
                '() => ({ scrollWidth: document.documentElement.scrollWidth, '
                'clientWidth: document.documentElement.clientWidth })'
            )
            assert dimensions['scrollWidth'] <= dimensions['clientWidth']

        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(trigger).to_be_focused()


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
            lambda response: (
                '/notifications/' in response.url
                and response.request.method == 'GET'
                and response.request.headers.get('hx-request') == 'true'
            )
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
            lambda response: (
                '/notifications/' in response.url
                and 'search=browser' in response.url
                and response.request.method == 'GET'
                and response.request.headers.get('hx-request') == 'true'
            )
        ):
            search_control.press_sequentially('browser')
        expect(page.locator('#notification-center-search')).to_be_visible()
        expect(page.get_by_role('navigation', name='Notification Center pagination')).to_be_visible()
