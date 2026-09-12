from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_authenticated_shell_has_independent_mobile_navigation_state() -> None:
    shell = _read('app/templates/layouts/app.html')

    assert 'mobileNavOpen: false' in shell
    assert 'openMobileNavigation()' in shell
    assert 'closeMobileNavigation()' in shell
    assert "@keydown.escape.window=\"if (mobileNavOpen)" in shell
    assert 'data-mobile-navigation-backdrop' in shell


def test_sidebar_is_off_canvas_on_mobile_and_persistent_on_desktop() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')

    assert 'data-mobile-navigation' in sidebar
    assert 'fixed inset-y-2 left-2' in sidebar
    assert 'lg:relative' in sidebar
    assert 'lg:translate-x-0' in sidebar
    assert ':class="mobileNavOpen ?' in sidebar
    assert 'data-mobile-navigation-close' in sidebar
    assert '@click="closeMobileNavigation()"' in sidebar


def test_navbar_exposes_mobile_menu_without_reusing_desktop_collapse_control() -> None:
    navbar = _read('app/templates/components/navigation/navbar.html')

    assert 'data-mobile-menu-trigger' in navbar
    assert '@click="openMobileNavigation()"' in navbar
    assert 'lg:hidden' in navbar
    assert 'hidden lg:inline-flex' in navbar
    assert 'aria-controls="app-sidebar"' in navbar
    assert 'data-mobile-current-page' in navbar


def test_mobile_shell_keeps_content_full_width_and_prevents_page_overflow() -> None:
    shell = _read('app/templates/layouts/app.html')

    assert 'min-w-0' in shell
    assert 'w-full' in shell
    assert 'overflow-x-hidden' in shell
    assert 'p-3 sm:p-4 lg:p-2' in shell


def test_shared_hero_recomposes_without_fixed_mobile_height() -> None:
    hero = _read('app/templates/components/page_hero.html')

    assert 'min-h-0 lg:min-h-[15.5rem]' in hero
    assert 'min-h-0 lg:min-h-[13rem]' in hero
    assert 'grid-cols-1 sm:grid-cols-2' in hero
    assert 'text-2xl' in hero
    assert 'sm:text-3xl' in hero
    assert 'lg:text-4xl' in hero
