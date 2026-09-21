from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_sidebar_owns_independent_mobile_navigation_state() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    assert 'mobileNavOpen: false' in sidebar
    assert 'mobileNavTrigger: null' in sidebar
    assert '@kaori:mobile-nav-open.window="openMobileNavigation($event)"' in sidebar
    assert '@keydown.escape.window="if (mobileNavOpen) closeMobileNavigation()"' in sidebar
    assert 'sidebarExpanded = false; openMobileNavigation($event)' not in sidebar
    assert 'restoreDesktopSidebarState()' not in sidebar
    assert 'this.$refs.mobileNavClose?.focus()' in sidebar
    assert 'this.mobileNavTrigger?.focus()' in sidebar
    assert 'data-mobile-navigation-backdrop' in sidebar
    app_layout = _read('app/templates/layouts/app.html')
    styles = _read('frontend/styles.css')
    assert (
        '@keydown.escape.window="if (window.innerWidth < 1024 && sidebarExpanded) { toggleSidebar() }"'
        not in app_layout
    )
    assert '@media (min-width: 64rem)' in styles
    assert '[data-mobile-navigation][x-cloak]' in styles


def test_sidebar_is_off_canvas_on_mobile_and_preserves_desktop_collapse_authority() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    assert 'data-mobile-navigation' in sidebar
    assert 'fixed inset-y-2 left-2' in sidebar
    assert 'lg:relative' in sidebar
    assert 'lg:visible' in sidebar
    assert 'lg:translate-x-0' in sidebar
    assert "'visible translate-x-0'" in sidebar
    assert "'invisible -translate-x-[calc(100%+1rem)]'" in sidebar
    assert '<aside x-cloak' in sidebar
    assert 'lg:[.sidebar-collapsed_&]:w-[78px]' in sidebar
    assert ' [.sidebar-collapsed_&]:w-[78px]' not in sidebar
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


def test_shared_hero_keeps_phone_density_compact_without_forking_authority() -> None:
    hero = _read('app/templates/components/page_hero.html')
    assert 'p-4' in hero
    assert 'sm:min-h-[15.5rem]' in hero
    assert 'sm:p-5' in hero
    assert 'lg:min-h-[17.5rem]' in hero
    assert 'lg:p-6' in hero
    assert 'grid gap-4 sm:min-h-[13rem] sm:gap-5 lg:min-h-[14.5rem]' in hero
    assert 'min-h-[15.5rem] overflow-hidden' not in hero
    assert 'grid min-w-0 grid-cols-1 gap-y-3' in hero
    assert 'sm:grid-cols-[56px_minmax(0,1fr)]' in hero
    assert 'hidden h-12 w-12' in hero
    assert 'sm:flex' in hero
    assert 'text-2xl font-bold leading-8' in hero
    assert 'sm:text-4xl sm:leading-10' in hero
    assert 'max-w-[44rem] text-sm font-normal leading-6' in hero
    assert 'sm:text-base sm:leading-7' in hero
    assert '[&>*:nth-child(n+2)]:hidden' in hero
    assert 'sm:[&>*:nth-child(n+2)]:inline-flex' in hero
    assert 'grid grid-cols-1 gap-2' in hero
    assert 'sm:grid-cols-2 sm:auto-rows-fr' in hero
    assert 'sm:[&>*:nth-child(n+2)]:block' in hero
    assert 'hidden sm:block' in hero
    assert 'min-h-[13rem] flex-col gap-3' not in hero


def test_welcome_uses_the_shared_page_hero_without_custom_mobile_title() -> None:
    welcome = _read('app/templates/welcome/index.html')
    assert 'page_hero.shell_classes()' in welcome
    assert 'page_hero.title_classes()' in welcome
    assert 'page_hero.description_classes()' in welcome
    assert 'data-mobile-page-intro' not in welcome
    assert '<h1 class="text-2xl' not in welcome
