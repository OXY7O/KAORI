from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Locator, Page, expect

from app.extensions import limiter

EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
TEST_USERNAME = 'browser-admin'
TEST_PASSWORD = 'browser-password'


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
    assert '/auth/login' not in page.url


def _visible_button(page: Page, accessible_name: str) -> Locator:
    return page.locator(f'button[aria-label="{accessible_name}"]:visible').first


def test_user_menu_is_accessible_disclosure_and_escape_restores_focus(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """User menu exposes disclosure state and returns focus after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'user-menu-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = page.get_by_role('button', name='Open user menu')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'user-menu')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        menu = page.locator('#user-menu')
        expect(menu).to_be_visible()

        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_quick_actions_disclosure_restores_focus_after_escape(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Quick Actions exposes ownership and restores its visible trigger after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'quick-actions-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = _visible_button(page, 'Open quick actions')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'quick-actions-menu')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        menu = page.locator('#quick-actions-menu')
        expect(menu).to_be_visible()
        menu.locator('a, button').first.focus()

        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_global_search_dialog_restores_trigger_focus_after_escape(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Global Search owns its dialog, focuses search, and restores its trigger after Escape."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'global-search-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = _visible_button(page, 'Open global search')
        expect(trigger).to_be_visible()
        expect(trigger).to_have_attribute('aria-controls', 'global-search')
        expect(trigger).to_have_attribute('aria-expanded', 'false')

        trigger.focus()
        trigger.press('Enter')
        expect(trigger).to_have_attribute('aria-expanded', 'true')

        dialog = page.get_by_role('dialog', name='Search KAORI')
        search_input = page.get_by_role('combobox', name='Search KAORI resources and pages')
        expect(dialog).to_be_visible()
        expect(search_input).to_be_focused()

        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(trigger).to_have_attribute('aria-expanded', 'false')
        expect(trigger).to_be_focused()


def test_global_search_keeps_keyboard_focus_inside_dialog(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Backward keyboard traversal cannot escape Global Search to the backdrop."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'global-search-focus-trap', viewport_name):
        _login(page, kaori_authenticated_base_url)

        trigger = _visible_button(page, 'Open global search')
        trigger.press('Enter')

        dialog = page.get_by_role('dialog', name='Search KAORI')
        search_input = page.get_by_role('combobox', name='Search KAORI resources and pages')
        expect(dialog).to_be_visible()
        expect(search_input).to_be_focused()

        page.keyboard.press('Shift+Tab')
        assert dialog.evaluate('(element) => element.contains(document.activeElement)') is True


def test_about_dialog_focus_is_contained_and_returns_to_user_menu_trigger(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """About dialog receives/traps focus and returns to the logical disclosure trigger."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'about-dialog-accessibility', viewport_name):
        _login(page, kaori_authenticated_base_url)

        user_trigger = page.get_by_role('button', name='Open user menu')
        user_trigger.press('Enter')
        about_trigger = page.get_by_role('button', name='About')
        expect(about_trigger).to_be_visible()
        about_trigger.press('Enter')

        dialog = page.get_by_role('dialog', name='About KAORI')
        expect(dialog).to_be_visible()
        expect(dialog).to_be_focused()

        close_button = dialog.get_by_role('button', name='Close About KAORI')
        close_button.focus()
        page.keyboard.press('Shift+Tab')
        assert dialog.evaluate('(element) => element.contains(document.activeElement)') is True

        page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        expect(user_trigger).to_be_focused()


def test_login_validation_errors_are_programmatically_associated(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Invalid login fields expose error state and reference their visible messages."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'login-validation-accessibility', viewport_name):
        reset_limiter = getattr(limiter, 'reset', None)
        assert callable(reset_limiter)
        reset_limiter()

        response = page.goto(f'{kaori_authenticated_base_url}/auth/login', wait_until='networkidle')
        assert response is not None
        assert response.ok

        username = page.get_by_label('Username', exact=True)
        password = page.get_by_label('Password', exact=True)
        expect(username).to_be_visible()
        expect(password).to_be_visible()

        username.fill('')
        password.fill('')
        login_form = username.locator('xpath=ancestor::form[1]')
        expect(login_form).to_be_visible()
        login_form.evaluate('(form) => HTMLFormElement.prototype.submit.call(form)')
        page.wait_for_load_state('networkidle')

        expect(username).to_have_attribute('aria-invalid', 'true')
        expect(username).to_have_attribute('aria-describedby', 'username-error')
        expect(password).to_have_attribute('aria-invalid', 'true')
        expect(password).to_have_attribute('aria-describedby', 'password-error')

        username_error = page.locator('#username-error')
        password_error = page.locator('#password-error')
        expect(username_error).to_be_visible()
        expect(password_error).to_be_visible()
        expect(username_error).to_have_attribute('role', 'alert')
        expect(password_error).to_have_attribute('role', 'alert')


def test_global_search_dynamic_feedback_is_programmatically_announced(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
    kaori_authenticated_base_url: str,
) -> None:
    """Loading, error, and empty search states expose live-region semantics."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'global-search-status-feedback', viewport_name):
        _login(page, kaori_authenticated_base_url)

        root = page.locator('#global-search')
        search_url = root.get_attribute('data-search-url')
        assert search_url
        page.route(f'**{search_url}*', lambda route: route.abort())

        trigger = _visible_button(page, 'Open global search')
        trigger.press('Enter')
        dialog = page.get_by_role('dialog', name='Search KAORI')
        expect(dialog).to_be_visible()

        error = dialog.locator('[x-show="searchError"]')
        expect(error).to_be_visible()
        expect(error).to_have_attribute('role', 'alert')
        expect(error).to_have_attribute('aria-live', 'assertive')
        expect(error).to_have_attribute('aria-atomic', 'true')

        loading = dialog.locator('[aria-label="Searching"]')
        expect(loading).to_have_attribute('role', 'status')
        expect(loading).to_have_attribute('aria-live', 'polite')
        expect(loading).to_have_attribute('aria-atomic', 'true')

        empty = dialog.get_by_text('No matching results', exact=True).locator('xpath=..')
        expect(empty).to_have_attribute('role', 'status')
        expect(empty).to_have_attribute('aria-live', 'polite')
        expect(empty).to_have_attribute('aria-atomic', 'true')


def test_side_drawer_controller_contains_and_restores_focus_across_viewports(
    configured_page: Page,
    kaori_viewport: tuple[str, tuple[int, int]],
) -> None:
    """Canonical side-drawer controller traps focus and restores the logical opener."""
    page = configured_page
    viewport_name, _ = kaori_viewport

    with _browser_evidence(page, 'side-drawer-focus-contract', viewport_name):
        page.set_content(
            """
            <div x-data="{ drawerOpen: false }">
                <button id="drawer-trigger" @click="drawerOpen = true">Open Drawer</button>
                <div
                    x-cloak
                    x-data="kaoriSideDrawer"
                    x-show="drawerOpen"
                    x-effect="syncOpen(Boolean(drawerOpen), $refs.dialog)"
                >
                    <button type="button" @click="drawerOpen = false">Backdrop</button>
                    <section
                        x-ref="dialog"
                        tabindex="-1"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Canonical Side Drawer"
                    >
                        <button id="drawer-first">First Action</button>
                        <button id="drawer-close" @click="drawerOpen = false">Close Drawer</button>
                    </section>
                </div>
            </div>
            """
        )
        page.add_script_tag(path='app/static/js/side_drawer.js')
        page.add_script_tag(path='app/static/vendor/alpine/alpine.min.js')

        trigger = page.locator('#drawer-trigger')
        first = page.locator('#drawer-first')
        close = page.locator('#drawer-close')
        dialog = page.get_by_role('dialog', name='Canonical Side Drawer')

        trigger.focus()
        trigger.click()
        expect(dialog).to_be_visible()
        expect(first).to_be_focused()

        close.focus()
        page.keyboard.press('Tab')
        expect(first).to_be_focused()

        page.keyboard.press('Shift+Tab')
        expect(close).to_be_focused()

        close.click()
        expect(dialog).to_be_hidden()
        expect(trigger).to_be_focused()
