from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_sidebar_owns_independent_mobile_navigation_state() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    assert 'mobileNavOpen: false' in sidebar
    assert 'mobileNavTrigger: null' in sidebar
    assert '@kaori:mobile-nav-open.window="sidebarExpanded = false; openMobileNavigation($event)"' in sidebar
    assert '@keydown.escape.window="if (mobileNavOpen) closeMobileNavigation()"' in sidebar
    assert 'restoreDesktopSidebarState()' in sidebar
    assert 'this.$refs.mobileNavClose?.focus()' in sidebar
    assert 'this.mobileNavTrigger?.focus()' in sidebar
    assert 'data-mobile-navigation-backdrop' in sidebar


def test_sidebar_is_off_canvas_on_mobile_and_preserves_desktop_collapse_authority() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    assert 'data-mobile-navigation' in sidebar
    assert 'fixed inset-y-2 left-2' in sidebar
    assert 'lg:relative' in sidebar
    assert 'lg:visible' in sidebar
    assert 'lg:translate-x-0' in sidebar
    assert "'visible translate-x-0'" in sidebar
    assert "'invisible -translate-x-[calc(100%+1rem)]'" in sidebar
    assert '[.sidebar-collapsed_&]:w-[78px]' in sidebar
    assert 'data-mobile-navigation-close' in sidebar
    assert '@click="closeMobileNavigation()"' in sidebar
    assert "$event.target.closest('a[href]')" in sidebar


def test_navbar_exposes_mobile_menu_without_reusing_desktop_collapse_control() -> None:
    navbar = _read('app/templates/components/navigation/navbar.html')
    assert 'data-mobile-menu-trigger' in navbar
    assert "$dispatch('kaori:mobile-nav-open', { trigger: $el })" in navbar
    assert 'lg:hidden' in navbar
    assert 'hidden h-10 w-10' in navbar
    assert 'lg:inline-flex' in navbar
    assert 'aria-controls="app-sidebar"' in navbar
    assert 'data-mobile-current-page' in navbar
    assert 'aria-label="Open quick actions"' in navbar
    assert 'id="theme-toggle"' in navbar
    assert 'aria-label="Open user menu"' in navbar
    assert 'class="{{ surface_ui.block_classes() }} inline-flex h-10 min-w-0' in navbar


def test_shared_hero_keeps_canonical_authority_for_every_viewport() -> None:
    hero = _read('app/templates/components/page_hero.html')
    assert 'min-h-[15.5rem]' in hero
    assert 'lg:min-h-[17.5rem]' in hero
    assert 'flex h-full min-h-[13rem] flex-col gap-3' in hero
    assert 'grid grid-cols-2 auto-rows-fr gap-2' in hero
    assert 'text-3xl font-bold leading-10' in hero
    assert 'max-w-[44rem] text-base font-normal leading-7' in hero


def test_welcome_uses_the_shared_page_hero_without_custom_mobile_title() -> None:
    welcome = _read('app/templates/welcome/index.html')
    assert 'page_hero.shell_classes()' in welcome
    assert 'page_hero.title_classes()' in welcome
    assert 'page_hero.description_classes()' in welcome
    assert 'data-mobile-page-intro' not in welcome
    assert '<h1 class="text-2xl' not in welcome
