from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import Page, expect

from tests.ui.visual_audit import (
    DETERMINISTIC_VISUAL_SURFACES,
    VisualAuditFinding,
    assert_document_fits_viewport,
    assert_locator_within_viewport,
    assert_hero_description_contract,
    assert_locator_within_document_width,
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
    page.evaluate('() => document.fonts.ready')
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

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


def test_welcome_catalog_content_search_and_card_geometry_across_canonical_viewports(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Exercise current Welcome content and catalog interaction across every canonical viewport."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'welcome-catalog-content-search', viewport_name):
        _login(page, kaori_authenticated_base_url)

        response = page.goto(f'{kaori_authenticated_base_url}/welcome', wait_until='networkidle')
        assert response is not None
        assert response.ok

        expect(page.get_by_role('heading', name='Welcome to KAORI')).to_be_visible()
        tenant_card = page.get_by_role('link', name='Open Tenant Management Workspace')
        access_card = page.get_by_role('link', name='Open Access Workspace')
        expect(tenant_card).to_be_visible()
        expect(access_card).to_be_visible()
        expect(tenant_card).to_contain_text('Governed Tenancy')
        expect(tenant_card).to_contain_text(re.compile(r'namespace provisioning', re.I))
        expect(access_card).to_contain_text(re.compile(r'identity providers', re.I))
        expect(access_card).to_contain_text('directory-projected external identities')

        assert_document_fits_viewport(page)
        cards = page.locator('[data-workspace-card]')
        assert cards.count() >= 2
        for index in range(cards.count()):
            card = cards.nth(index)
            if card.is_visible():
                assert_locator_within_document_width(page, card, label=f'Welcome workspace card #{index + 1}')

        search = page.locator('[data-workspace-search]')
        expect(search).to_be_visible()
        page.keyboard.press('/')
        expect(search).to_be_focused()
        search.fill('tenant')

        expect(tenant_card).to_be_visible()
        expect(access_card).to_be_hidden()
        expect(page.locator('[data-workspace-result-count]')).to_have_text('1 Workspace')
        assert_document_fits_viewport(page)

        page.keyboard.press('Escape')
        expect(search).to_have_value('')
        expect(search).not_to_be_focused()
        expect(tenant_card).to_be_visible()
        expect(access_card).to_be_visible()
        assert_document_fits_viewport(page)


def test_sidebar_v21_two_level_navigation_and_page_workspace_across_canonical_viewports(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Validate two-level sidebar disclosure and page-owned level-three navigation."""
    page = configured_page
    viewport_name, (width, _) = kaori_viewport

    with _browser_evidence(page, 'sidebar-v21-two-level-workspace', viewport_name):
        _login(page, kaori_authenticated_base_url)
        response = page.goto(f'{kaori_authenticated_base_url}/welcome', wait_until='networkidle')
        assert response is not None
        assert response.ok

        if width < 1024:
            page.locator('[data-mobile-menu-trigger]').click()

        sidebar = page.locator('#app-sidebar')
        expect(sidebar).to_be_visible()

        section_labels = sidebar.locator('[data-kaori-sidebar-section] .sidebar-section-label').all_inner_texts()
        assert section_labels == ['MAIN', 'INFRASTRUCTURE', 'INSIGHTS', 'PLATFORM', 'ADMINISTRATION']

        expect(sidebar.locator('[data-kaori-sidebar-workspace="welcome"]')).to_be_visible()
        for key in (
            'kubernetes',
            'object_storage',
            'intelligence',
            'reports',
            'operations_center',
            'integrations',
            'access',
            'settings',
        ):
            expect(sidebar.locator(f'[data-kaori-sidebar-workspace="{key}"]')).to_be_visible()

        kubernetes = sidebar.locator('[data-kaori-sidebar-workspace="kubernetes"]')
        kubernetes_trigger = kubernetes.locator('[data-kaori-sidebar-workspace-trigger="kubernetes"]')

        if width >= 1024:
            collapse = page.get_by_role('button', name='Collapse navigation')
            expect(collapse).to_be_visible()
            expanded_box = sidebar.bounding_box()
            assert expanded_box is not None

            collapse.click()
            expect(page.get_by_role('button', name='Expand navigation')).to_be_visible()
            collapsed_box = sidebar.bounding_box()
            assert collapsed_box is not None
            assert collapsed_box['width'] < expanded_box['width']

            kubernetes_trigger.click()
            expect(page.get_by_role('button', name='Collapse navigation')).to_be_visible()

        if not kubernetes.evaluate('element => element.open'):
            kubernetes_trigger.click()

        capability_region = kubernetes.locator('[data-kaori-sidebar-capabilities="kubernetes"]')
        expect(capability_region).to_be_visible()
        for label in ('Overview', 'Inventory', 'Operations', 'Governance', 'Tenant', 'Analytics'):
            expect(capability_region.get_by_role('link', name=label, exact=True)).to_be_visible()

        capability_region.get_by_role('link', name='Inventory', exact=True).click()
        page.wait_for_load_state('networkidle')

        expect(page.locator('[data-kaori-domain-workspace-nav]')).to_have_count(0)
        inventory_views = page.locator('[data-kaori-capability-navigation="kubernetes_inventory"]')
        expect(inventory_views).to_be_visible()
        expect(inventory_views.locator('[data-kaori-tab-variant="integrated-workspace-server"]')).to_be_visible()
        expect(inventory_views.locator('[data-kaori-tab-variant="content-tabs"]')).to_have_count(0)
        for label in (
            'Overview',
            'Topology',
            'Nodes',
            'Namespaces',
            'Workloads',
            'Pods',
            'Services',
            'Ingresses',
            'Storage',
            'Configuration',
        ):
            expect(inventory_views.get_by_role('link', name=label, exact=True)).to_be_visible()

        if width < 1024:
            page.locator('[data-mobile-menu-trigger]').click()
            sidebar = page.locator('#app-sidebar')
            expect(sidebar).to_be_visible()

        kubernetes = sidebar.locator('[data-kaori-sidebar-workspace="kubernetes"]')
        expect(kubernetes).to_have_attribute('open', '')
        expect(kubernetes.locator('[data-kaori-sidebar-capability="inventory"]')).to_have_attribute(
            'aria-current', 'page'
        )

        if width < 1024:
            page.locator('[data-mobile-navigation-close]').click()

        assert_document_fits_viewport(page)
        assert_locator_within_document_width(
            page,
            inventory_views,
            label='Kubernetes Inventory level-three navigation',
        )

        response = page.goto(f'{kaori_authenticated_base_url}/analytics/', wait_until='networkidle')
        assert response is not None
        assert response.ok
        if page.locator('[data-kaori-blocked-state]').count() > 0:
            analytics_blocked_views = page.locator('[data-kaori-capability-navigation="kubernetes_analytics"]')
            expect(analytics_blocked_views).to_be_visible()
            expect(
                analytics_blocked_views.locator('[data-kaori-tab-variant="integrated-workspace-server"]')
            ).to_be_visible()

        response = page.goto(
            f'{kaori_authenticated_base_url}/analytics/capacity?time_range=7d',
            wait_until='networkidle',
        )
        assert response is not None
        assert response.ok
        expect(page.locator('[data-kaori-domain-workspace-nav]')).to_have_count(0)

        analytics_views = page.locator('[data-kaori-capability-navigation="kubernetes_analytics"]')
        expect(analytics_views).to_be_visible()
        expect(analytics_views.get_by_role('link', name='Capacity', exact=True)).to_have_attribute(
            'aria-current',
            'page',
        )
        forecast_href = analytics_views.get_by_role('link', name='Forecast', exact=True).get_attribute('href')
        assert forecast_href is not None
        assert 'time_range=7d' in forecast_href

        response = page.goto(f'{kaori_authenticated_base_url}/intelligence/', wait_until='networkidle')
        assert response is not None
        assert response.ok
        expect(page.locator('[data-kaori-domain-workspace-nav]')).to_have_count(0)
        expect(page.locator('[data-kaori-capability-navigation]')).to_have_count(0)

        if width < 1024:
            page.locator('[data-mobile-menu-trigger]').click()
        sidebar = page.locator('#app-sidebar')
        intelligence = sidebar.locator('[data-kaori-sidebar-workspace="intelligence"]')
        expect(intelligence).to_have_attribute('open', '')
        intelligence_children = intelligence.locator('[data-kaori-sidebar-capabilities="intelligence"]')
        for label in ('Overview', 'Recommendations', 'Alert Intelligence', 'Rule Catalog', 'Automation Control'):
            expect(intelligence_children.get_by_role('link', name=label, exact=True)).to_be_visible()
        expect(intelligence.locator('[data-kaori-sidebar-capability="overview"]')).to_have_attribute(
            'aria-current', 'page'
        )

        if width < 1024:
            page.locator('[data-mobile-navigation-close]').click()

        response = page.goto(
            f'{kaori_authenticated_base_url}/storage/object-storage/',
            wait_until='networkidle',
        )
        assert response is not None
        assert response.ok
        expect(page.locator('[data-kaori-domain-workspace-nav]')).to_have_count(0)
        object_views = page.locator('[data-kaori-capability-navigation="object_storage_inventory"]')
        expect(object_views).to_be_visible()
        expect(object_views.locator('[data-kaori-tab-variant="integrated-workspace-server"]')).to_be_visible()
        for label in ('Overview', 'Systems', 'Buckets & Containers'):
            expect(object_views.get_by_role('link', name=label, exact=True)).to_be_visible()

        assert_document_fits_viewport(page)
        assert_locator_within_document_width(
            page,
            object_views,
            label='Object Storage Inventory level-three navigation',
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

        # Exercise and measure the *rendered* overlay after an HTMX refresh and
        # real user click, not only its static template or initial screenshot.
        assert_document_fits_viewport(page)
        assert_locator_within_viewport(page, dialog, label='Notification Deck dialog')
        tabs = dialog.locator('[data-notification-deck-tabs]')
        footer = dialog.locator('[data-notification-deck-footer]')
        expect(tabs).to_be_visible()
        expect(footer).to_be_visible()
        assert_locator_within_document_width(page, tabs, label='Notification Deck tabs')
        assert_locator_within_document_width(page, footer, label='Notification Deck footer')
        page.screenshot(
            path=str(EVIDENCE_ROOT / f'authenticated-htmx-overlay-open-{viewport_name}.png'),
            full_page=True,
            animations='disabled',
        )
        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(modal_trigger).to_be_focused()


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
        expect(page.locator('#notification-center-search')).to_have_value('browser')
        expect(page.get_by_role('navigation', name='Notification Center pagination')).to_be_visible()
        clear = page.locator('[data-kaori-clear-filters]')
        expect(clear).to_be_visible()
        page.screenshot(
            path=str(EVIDENCE_ROOT / f'authenticated-filter-search-{viewport_name}.png'),
            full_page=True,
            animations='disabled',
        )

        with page.expect_response(
            lambda response: (
                '/notifications/' in response.url
                and 'search=browser' not in response.url
                and response.request.headers.get('hx-request') == 'true'
            )
        ) as cleared_response:
            clear.click()
        assert cleared_response.value.ok
        expect(page.locator('#notification-center-search')).to_have_value('')
        expect(page.locator('[data-kaori-clear-filters]')).to_have_count(0)
        assert_document_fits_viewport(page)


def test_notification_center_filters_and_rows_survive_htmx_reset(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """UAT-UIX-006: actual select/click requests preserve Rows and reset filters."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'uat-uix-006-notification-filter-reset', viewport_name):
        _login(page, kaori_authenticated_base_url)
        _open_notification_center(page, kaori_authenticated_base_url)

        status = page.locator('#notification-center-status')
        rows = page.locator('#notification-center-per-page')
        expect(status).to_have_value('all')
        expect(rows).to_have_value('5')

        with page.expect_response(
            lambda response: (
                '/notifications/' in response.url
                and 'status=error' in response.url
                and response.request.headers.get('hx-request') == 'true'
            )
        ) as filtered_response:
            status.select_option('error')
        assert filtered_response.value.ok
        expect(page.locator('#notification-center-status')).to_have_value('error')
        expect(page.locator('[data-kaori-clear-filters]')).to_be_visible()
        page.screenshot(
            path=str(EVIDENCE_ROOT / f'uat-uix-006-filtered-{viewport_name}.png'),
            full_page=True,
            animations='disabled',
        )

        with page.expect_response(
            lambda response: (
                '/notifications/' in response.url
                and 'per_page=10' in response.url
                and 'status=error' in response.url
                and response.request.headers.get('hx-request') == 'true'
            )
        ) as rows_response:
            page.locator('#notification-center-per-page').select_option('10')
        assert rows_response.value.ok
        expect(page.locator('#notification-center-per-page')).to_have_value('10')
        expect(page.locator('#notification-center-status')).to_have_value('error')

        with page.expect_response(
            lambda response: (
                '/notifications/' in response.url
                and 'per_page=10' in response.url
                and 'status=error' not in response.url
                and response.request.headers.get('hx-request') == 'true'
            )
        ) as clear_response:
            page.locator('[data-kaori-clear-filters]').click()
        assert clear_response.value.ok
        expect(page.locator('#notification-center-status')).to_have_value('all')
        expect(page.locator('#notification-center-per-page')).to_have_value('10')
        expect(page.locator('[data-kaori-clear-filters]')).to_have_count(0)
        assert_document_fits_viewport(page)
        expect(page.get_by_text('No Matching Notifications')).to_be_visible()


def test_failed_generated_report_detail_is_truthful_and_responsive(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """UAT-RPT-003: render the real failed-detail template in a controlled browser."""
    page = configured_page
    viewport_name, _ = kaori_viewport
    report_id = 47
    failure_message = 'Report queue registration failed in the isolated QA fixture.'
    payload = {
        'page_title': 'Report Detail',
        'page_subtitle': 'Review report metadata, artifacts, and recovery evidence.',
        'registry_return_url': '/reports/generated',
        'poll_interval_seconds': None,
        'job_execution': None,
        'artifact_access_notice': None,
        'report': {
            'id': report_id,
            'name': 'Controlled Failed Report',
            'raw_status': 'failed',
            'status': 'Failed',
            'report_icon': 'file-x',
            'report_type': 'Inventory Overview',
            'scope': 'QA Fixture',
            'scope_label': 'Cluster',
            'secondary_scope': 'All Namespaces',
            'period': '30 days',
            'output_format': 'CSV',
            'artifact_label': 'CSV',
            'generate_artifact_label': 'Generate Artifact',
            'file_state': {'icon': 'file-x', 'tone': 'red', 'label': 'Not Generated'},
            'can_download_artifact': False,
            'can_generate_artifact': False,
            'can_restore_report': False,
            'can_archive_report': False,
            'file_path': None,
            'file_exists': False,
            'file_size': 'N/A',
            'storage_backend_label': 'No Artifact',
            'storage_object_key': 'N/A',
            'storage_uri_display': 'N/A',
            'generated_by': 'QA Fixture Operator',
            'generated_by_meta': {'status_label': 'Test Fixture'},
            'created_at': '2026-10-13',
            'sections': [{'label': 'Inventory Assets'}],
            'sections_count': 1,
            'error_message': failure_message,
        },
    }

    with (
        patch('app.reports.generated.routes.get_report_detail_payload', return_value=payload),
        _browser_evidence(page, 'uat-rpt-003-failed-report-detail', viewport_name),
    ):
        _login(page, kaori_authenticated_base_url)
        response = page.goto(
            f'{kaori_authenticated_base_url}/reports/generated/{report_id}',
            wait_until='networkidle',
        )
        assert response is not None
        assert response.ok

        detail = page.locator('[data-generated-report-detail]')
        expect(detail).to_be_visible()
        expect(page.get_by_role('heading', name='Controlled Failed Report')).to_be_visible()
        expect(page.locator('[data-generated-detail-generation-note]')).to_contain_text(
            failure_message
        )
        expect(page.get_by_text('No Job Execution Linked', exact=True)).to_be_visible()
        expect(page.locator('[data-generated-detail-primary-action="download"]')).to_have_count(0)
        expect(page.locator('[data-generated-detail-primary-action="regenerate"]')).to_have_count(0)
        assert detail.get_attribute('hx-trigger') is None
        assert_document_fits_viewport(page)
        assert_locator_within_document_width(
            page,
            page.locator('[data-generated-detail-report-actions]'),
            label='Failed report detail actions',
        )
        page.screenshot(
            path=str(EVIDENCE_ROOT / f'uat-rpt-003-failed-detail-light-{viewport_name}.png'),
            full_page=True,
            animations='disabled',
        )

        _load_persisted_visual_theme(page, 'dark')
        expect(page.locator('[data-generated-detail-generation-note]')).to_contain_text(
            failure_message
        )
        expect(page.locator('[data-generated-detail-primary-action="download"]')).to_have_count(0)
        assert page.locator('[data-generated-report-detail]').get_attribute('hx-trigger') is None
        assert_document_fits_viewport(page)


def test_reports_generate_wizard_negative_submission_is_scoped_and_reviewable(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """UAT-RPT-001/003: real wizard clicks, scope selection and bounded rejection."""
    import app.reports.generate.service as report_service

    page = configured_page
    viewport_name, _ = kaori_viewport
    submitted: list[dict[str, str]] = []

    def reject_request(form, _user_id):
        submitted.append(form.to_dict())
        return False, ['Isolated QA contract rejects queue admission; no report was saved.'], None

    with (
        patch(
            'app.reports.generate.service._get_storage_generation_context',
            return_value={
                'backend': 'isolated', 'label': 'Disposable test storage',
                'status': 'Ready', 'tone': 'blue', 'description': 'Test fixture only.',
                'ready': True, 'state': 'ready', 'source': 'test', 'checked_at': None,
            },
        ),
        patch(
            'app.reports.generate.service.get_queue_readiness',
            return_value={'show_warning': False},
        ),
        patch(
            'app.reports.generate.service._get_cluster_options',
            return_value=[{'value': 'qa-cluster', 'label': 'QA Disposable Cluster'}],
        ),
        patch('app.reports.generate.service._get_object_storage_system_options', return_value=[]),
        patch('app.reports.generate.service.get_active_registry_options', return_value=[]),
        patch(
            'app.reports.generate.service._get_namespace_options_by_cluster',
            return_value={'qa-cluster': ['qa-namespace']},
        ),
        patch('app.reports.generate.routes.create_report_request', side_effect=reject_request),
        patch('app.reports.generate.routes.queue_transient_feedback', return_value=None),
        _browser_evidence(page, 'uat-rpt-001-003-wizard-rejection', viewport_name),
    ):
        _login(page, kaori_authenticated_base_url)
        response = page.goto(f'{kaori_authenticated_base_url}/reports/generate', wait_until='networkidle')
        assert response is not None and response.ok

        form = page.locator('#generate-report-form')
        expect(form).to_be_visible()
        page.locator('#report-type-select').select_option('analytics_overview')
        page.locator('#report-name-input').fill('QA Controlled Analytics')
        page.locator('#wizard-next-button').click()
        expect(page.locator('[data-wizard-panel="2"]')).to_be_visible()

        # A required cluster must not be silently substituted by the browser.
        page.locator('#wizard-next-button').click()
        expect(page.locator('[data-wizard-panel="2"]')).to_be_visible()
        expect(page.locator('#wizard-scope-validation')).to_be_visible()
        page.locator('#cluster-select').select_option('qa-cluster')
        page.locator('#namespace-select').select_option('qa-namespace')

        for step in ('3', '4', '5'):
            page.locator('#wizard-next-button').click()
            expect(page.locator(f'[data-wizard-panel="{step}"]')).to_be_visible()
            assert_document_fits_viewport(page)

        page.locator('#output-format-select').select_option('csv')
        expect(page.locator('#generate-report-button')).to_be_enabled()
        expect(page.locator('#preview-report-name')).to_contain_text('QA Controlled Analytics')
        page.screenshot(
            path=str(EVIDENCE_ROOT / f'uat-rpt-001-003-wizard-review-{viewport_name}.png'),
            full_page=True,
            animations='disabled',
        )
        page.locator('#generate-report-button').click()
        expect(page.get_by_label('Unable to create report request')).to_be_visible()
        expect(page.get_by_text('Isolated QA contract rejects queue admission; no report was saved.')).to_be_visible()

        assert len(submitted) == 1
        assert submitted[0]['report_type'] == 'analytics_overview'
        assert submitted[0]['cluster_id'] == 'qa-cluster'
        assert submitted[0]['namespace'] == 'qa-namespace'
        assert submitted[0]['name'] == 'QA Controlled Analytics'
        assert submitted[0]['output_format'] == 'csv'
        assert_document_fits_viewport(page)


def test_tenant_namespace_form_rejected_submit_records_no_provider_write(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """UAT-TEN-004 partial: use real Tenant form markup and actual rejected HTTP POST."""
    from types import SimpleNamespace

    import app.kubernetes.tenant.routes as tenant_routes

    page = configured_page
    viewport_name, _ = kaori_viewport
    submitted: list[dict[str, str]] = []
    audit: list[dict[str, object]] = []
    render_original = tenant_routes.render_template

    def render_isolated_tenant_form(template_name, **context):
        if template_name == 'kubernetes/tenant/namespace_provisioning.html':
            return render_original(
                'kubernetes/tenant/partials/_namespace_form.html',
                environment_options=[
                    SimpleNamespace(
                        id=14,
                        tenant=SimpleNamespace(name='QA Disposable Tenant'),
                        environment='dev',
                    )
                ],
                profiles=[
                    SimpleNamespace(
                        id=18, name='QA Bounded Profile',
                        enabled=True, profile_class='custom', version=1,
                    )
                ],
                can_manage=True,
                native_available=True,
            )
        return render_original(template_name, **context)

    def reject_before_provider_write(form):
        submitted.append(form.to_dict())
        raise ValueError('Capacity preflight rejected the isolated Namespace request.')

    with (
        patch('app.kubernetes.tenant.routes._tenant_workspace_context', return_value={}),
        patch('app.kubernetes.tenant.routes.get_namespace_provisioning_support_context', return_value={}),
        patch('app.kubernetes.tenant.routes.get_capsule_shared_allocation_context', return_value={}),
        patch('app.kubernetes.tenant.routes.get_capsule_tenant_quota_context', return_value={}),
        patch('app.kubernetes.tenant.routes.get_namespace_registry_context', return_value={}),
        patch('app.kubernetes.tenant.routes.render_template', side_effect=render_isolated_tenant_form),
        patch('app.kubernetes.tenant.routes._csrf', return_value=None),
        patch(
            'app.kubernetes.tenant.routes.provision_native_namespace_committed',
            side_effect=reject_before_provider_write,
        ),
        patch(
            'app.kubernetes.tenant.routes._record',
            side_effect=lambda **item: audit.append(item),
        ),
        _browser_evidence(page, 'uat-ten-004-namespace-form-rejection', viewport_name),
    ):
        _login(page, kaori_authenticated_base_url)
        response = page.goto(
            f'{kaori_authenticated_base_url}/kubernetes/tenant/namespace-provisioning',
            wait_until='networkidle',
        )
        assert response is not None and response.ok
        form = page.locator('[data-tenant-namespace-allocation-form]')
        expect(form).to_be_visible()
        form.locator('[name="tenant_environment_id"]').select_option('14')
        form.locator('[name="resource_profile_id"]').select_option('18')
        form.locator('[name="namespace"]').fill('qa-disposable-namespace')
        expect(form.get_by_role('button', name='Create & Verify')).to_be_enabled()
        form.get_by_role('button', name='Create & Verify').click()
        page.wait_for_load_state('networkidle')

        # The real route rejects via the service boundary; provider calls are
        # impossible in this isolated fixture and no successful audit is emitted.
        assert len(submitted) == 1
        assert submitted[0]['tenant_environment_id'] == '14'
        assert submitted[0]['resource_profile_id'] == '18'
        assert submitted[0]['namespace'] == 'qa-disposable-namespace'
        assert len(audit) == 1
        assert audit[0]['event_type'] == 'kubernetes_tenant_namespace_provision_failed'
        assert audit[0]['status'] == 'error'
        expect(page.locator('[data-tenant-namespace-allocation-form]')).to_be_visible()
