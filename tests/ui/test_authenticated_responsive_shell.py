from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_AUTH_INPUT = 'ui-test-input'
ADAPTIVE_VIEWPORTS = {'tablet', 'mobile', 'small-mobile'}


def _login(page: Page, base_url: str) -> None:
    response = page.goto(f'{base_url}/auth/login', wait_until='domcontentloaded')
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
    # Assert authenticated navigation and rendered app shell rather than idle network.
    expect(page).not_to_have_url(re.compile(r'/auth/login(?:[/?#]|$)'))
    # The sidebar is intentionally hidden on tablet/mobile until navigation opens.
    # Require the authenticated Welcome workspace to be rendered at every viewport.
    expect(page.get_by_role('heading', name='Welcome to KAORI')).to_be_visible()
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


def test_secrets_pki_lifecycle_1440_hero_context_is_single_line_and_navigation_is_shared(
    page: Page,
    kaori_authenticated_base_url: str,
) -> None:
    # Rendered geometry, not CSS nowrap/ellipsis, is the final density authority.
    page.set_viewport_size({'width': 1440, 'height': 900})
    _login(page, kaori_authenticated_base_url)
    response = page.goto(f'{kaori_authenticated_base_url}/secrets-pki/lifecycle', wait_until='domcontentloaded')
    assert response is not None and response.ok

    navigation = page.locator('#secrets-pki-lifecycle nav[data-kaori-tab-variant="integrated-workspace-server"]')
    expect(navigation).to_be_visible()
    expect(navigation.locator('a[aria-current="page"]')).to_have_text('Lifecycle & Assurance')
    assert navigation.locator('a').count() == 4

    hero = page.locator('#secrets-pki-lifecycle section.kaori-hero-shell')
    expect(hero).to_be_visible()
    targets = hero.locator(
        '.kaori-hero-panel h2, [data-kaori-hero-context-metric] p, .kaori-hero-panel > .kaori-hero-tile p'
    )
    assert targets.count() == 8
    for element in targets.all():
        expect(element).to_be_visible()
        measurement = element.evaluate(
            """el => {
                const styles = getComputedStyle(el);
                const box = el.getBoundingClientRect();
                return {
                    height: box.height,
                    lineHeight: parseFloat(styles.lineHeight),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    whiteSpace: styles.whiteSpace,
                    overflow: styles.overflow,
                    textOverflow: styles.textOverflow
                };
            }"""
        )
        assert measurement['whiteSpace'] != 'nowrap', measurement
        assert measurement['textOverflow'] != 'ellipsis', measurement
        assert measurement['overflow'] != 'hidden', measurement
        assert measurement['height'] <= measurement['lineHeight'] + 1.5, measurement
        assert measurement['scrollWidth'] <= measurement['clientWidth'] + 1, measurement

    _assert_no_document_overflow(page)
    _capture(page, 'secrets-pki-lifecycle-hero', 'large-desktop')


def test_secrets_pki_overview_1440_blocked_hero_and_canonical_prerequisite(
    page: Page,
    kaori_authenticated_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Render the real Overview route against deterministic, unqualified
    # committed-state evidence. The shared authenticated UI server has no
    # PostgreSQL service and must not depend on a developer's local database.
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_secrets_pki_operational_summary',
        lambda: {'provider_count': 0, 'has_evidence': False},
    )
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_vault_binding_coverage',
        lambda: {
            'metrics': {'label': 'Vault Provider Not Configured'},
            'alerts': {'label': 'Vault Provider Not Configured'},
        },
    )
    monkeypatch.setattr('app.secrets_pki.routes.build_vault_alert_source_sample_summary', lambda: None)

    page.set_viewport_size({'width': 1440, 'height': 900})
    _login(page, kaori_authenticated_base_url)
    response = page.goto(f'{kaori_authenticated_base_url}/secrets-pki/', wait_until='domcontentloaded')
    assert response is not None and response.ok

    hero = page.locator('#secrets-pki-overview section.kaori-hero-shell')
    expect(hero).to_be_visible()
    assert hero.get_attribute('data-kaori-hero-profile') == 'operational-dashboard'
    assert hero.get_attribute('data-kaori-hero-state') == 'blocked'

    blocker = page.locator('#secrets-pki-overview section[data-kaori-blocked-state]')
    expect(blocker).to_be_visible()
    expect(blocker.get_by_role('heading', name='Committed KV v2 Inventory Required')).to_be_visible()
    assert page.locator('#secrets-pki-overview [data-kaori-empty-state]').count() == 0
    expect(blocker.get_by_role('link', name='Configure Vault Integrations')).to_be_visible()

    # DOM geometry is the final authority; never hide wrapping with nowrap/ellipsis.
    targets = hero.locator(
        '.kaori-hero-panel h2, .kaori-hero-panel [data-kaori-hero-context-metric] p, '
        '.kaori-hero-panel > .kaori-hero-tile p'
    )
    assert targets.count() == 8
    for item in targets.all():
        expect(item).to_be_visible()
        dimensions = item.evaluate(
            """el => {
                const style = getComputedStyle(el);
                const bounds = el.getBoundingClientRect();
                return {
                    height: bounds.height,
                    lineHeight: parseFloat(style.lineHeight),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    whiteSpace: style.whiteSpace,
                    overflow: style.overflow,
                    textOverflow: style.textOverflow
                };
            }"""
        )
        assert dimensions['height'] <= dimensions['lineHeight'] + 1.5, dimensions
        assert dimensions['scrollWidth'] <= dimensions['clientWidth'] + 1, dimensions
        assert dimensions['whiteSpace'] != 'nowrap', dimensions
        assert dimensions['overflow'] != 'hidden', dimensions
        assert dimensions['textOverflow'] != 'ellipsis', dimensions
    _assert_no_document_overflow(page)
    _capture(page, 'secrets-pki-overview-blocked', 'large-desktop')



@pytest.mark.parametrize(
    ('workspace', 'blocked_title', 'hidden_metric'),
    [
        ('inventory', 'Vault Inventory Source Required', 'Enabled Vault Sources'),
        ('lifecycle', 'Vault Lifecycle Source Required', 'Expires Within 7 Days'),
    ],
)
def test_secrets_pki_no_vault_source_1440_uses_canonical_blocker(
    page: Page,
    kaori_authenticated_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
    workspace: str,
    blocked_title: str,
    hidden_metric: str,
) -> None:
    # A real authenticated Flask + Chromium render, with only external
    # committed-read-model seams replaced. No PostgreSQL or Vault is needed.
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_secrets_pki_operational_summary',
        lambda: {'provider_count': 0, 'has_evidence': False},
    )
    monkeypatch.setattr('app.secrets_pki.routes.pki_public_readiness', lambda: {})
    monkeypatch.setattr('app.secrets_pki.routes.stored_pki_certificate_readiness', lambda: {})
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_kv2_version_posture',
        lambda: {'status': 'not_configured', 'label': 'Approved KV v2 Source Required'},
    )
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_stored_pki_validity_posture',
        lambda: {'status': 'not_configured', 'label': 'PKI Stored Certificates Not Enabled'},
    )
    monkeypatch.setattr(
        'app.secrets_pki.routes.build_certificate_delivery_overlap',
        lambda **_kwargs: {'status': 'source_unknown', 'label': 'Not Qualified'},
    )

    page.set_viewport_size({'width': 1440, 'height': 900})
    _login(page, kaori_authenticated_base_url)
    route = '/secrets-pki/inventory' if workspace == 'inventory' else '/secrets-pki/lifecycle'
    response = page.goto(f'{kaori_authenticated_base_url}{route}', wait_until='domcontentloaded')
    assert response is not None and response.ok

    root = page.locator(f'#secrets-pki-{workspace}')
    hero = root.locator('section.kaori-hero-shell')
    expect(hero).to_be_visible()
    expect(hero.locator('.kaori-hero-status-badge')).to_contain_text('Blocked')
    blocker = root.locator('section[data-kaori-blocked-state]')
    expect(blocker.get_by_role('heading', name=blocked_title)).to_be_visible()
    expect(blocker.get_by_role('link', name='Configure Vault Integrations')).to_be_visible()
    assert root.get_by_text(hidden_metric, exact=True).count() == 0
    assert root.locator('[data-kaori-empty-state]').count() == 0

    labels = hero.locator(
        '.kaori-hero-panel h2, .kaori-hero-panel [data-kaori-hero-context-metric] p, '
        '.kaori-hero-panel > .kaori-hero-tile p'
    )
    assert labels.count() == 8
    for label in labels.all():
        metrics = label.evaluate(
            """el => {
                const style = getComputedStyle(el);
                return {
                    height: el.getBoundingClientRect().height,
                    lineHeight: parseFloat(style.lineHeight),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    whiteSpace: style.whiteSpace,
                    overflow: style.overflow,
                    textOverflow: style.textOverflow
                };
            }"""
        )
        assert metrics['height'] <= metrics['lineHeight'] + 1.5, metrics
        assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1, metrics
        assert metrics['whiteSpace'] != 'nowrap', metrics
        assert metrics['overflow'] != 'hidden', metrics
        assert metrics['textOverflow'] != 'ellipsis', metrics

    _assert_no_document_overflow(page)
    _capture(page, f'secrets-pki-{workspace}-no-vault-source', 'large-desktop')
