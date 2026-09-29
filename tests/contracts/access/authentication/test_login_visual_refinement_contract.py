from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'partials'
CSS = ROOT / 'app' / 'static' / 'css' / 'auth-login.css'
FABRIC = ROOT / 'app' / 'static' / 'images' / 'kaori-login-operations-fabric.svg'
LOGIN_FORM = TEMPLATES / '_login_form.html'
INDEX = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'index.html'
BRAND_PANEL = TEMPLATES / '_brand_panel.html'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_login_brand_panel_uses_operations_fabric_visual() -> None:
    source = _read(TEMPLATES / '_brand_panel.html')

    assert 'images/kaori-login-operations-fabric.svg' in source
    assert 'kaori-operations-fabric' in source
    assert 'Operate with <span class="kaori-login-brand__clarity">Clarity</span>.' in source
    assert 'Infrastructure Operations Platform' in source
    assert 'Unified visibility and governed operations' in source
    assert 'Knowledge · Automation · Operations · Resilience · Intelligence' in source
    assert 'Governed Operations · Observable Evidence · Accountable Access' in source
    assert 'kaori-brand-network' not in source


def test_login_brand_heading_is_explicit_intentional_brand_authority() -> None:
    source = _read(TEMPLATES / '_brand_panel.html')

    assert 'data-kaori-auth-brand-heading-authority="intentional-brand-lockup"' in source
    assert 'class="mt-2 max-w-md text-2xl font-bold leading-tight tracking-tight xl:text-3xl"' in source


def test_login_brand_message_remains_global_not_provider_catalog() -> None:
    combined = _read(TEMPLATES / '_brand_panel.html') + _read(TEMPLATES / '_feature_cards.html')

    for capability in ('Visibility', 'Control', 'Intelligence', 'Assurance'):
        assert capability in combined

    for provider_or_workspace in (
        'Prometheus',
        'Alertmanager',
        'Kubernetes Analytics',
        'Secret Management',
        'TLS Governance',
    ):
        assert provider_or_workspace not in combined


def test_login_visual_uses_kaori_violet_and_keeps_compact_form_scale() -> None:
    css = _read(CSS)

    assert '.kaori-operations-fabric' in css
    assert '#7C3AED' in css
    assert '#A78BFA' in css
    assert 'width: min(1060px, 100%);' in css
    assert 'height: 44px;' in css
    assert 'min-height: 44px;' in css
    assert 'white-space: nowrap;' in css
    assert '.kaori-login-brand__clarity' in css
    assert 'color: #A78BFA;' in css


def test_login_visible_labels_use_title_case() -> None:
    brand = _read(TEMPLATES / '_brand_panel.html')
    form = _read(LOGIN_FORM)

    assert 'Infrastructure Operations Platform' in brand
    assert 'Knowledge · Automation · Operations · Resilience · Intelligence' in brand
    assert 'Governed Operations · Observable Evidence · Accountable Access' in brand
    assert 'Remember Me' in form
    assert 'Or Continue With' in form
    assert 'Authentication Activity Is Recorded for Audit' in form
    assert 'font-semibold uppercase tracking-wider text-content-disabled">Or Continue With' not in form


def test_operations_fabric_is_static_non_scripted_svg() -> None:
    source = _read(FABRIC)

    assert '<svg' in source
    assert '<script' not in source.lower()
    assert 'onload=' not in source.lower()
    assert 'href="http' not in source.lower()


def test_login_sso_region_has_explicit_zero_one_two_provider_geometry() -> None:
    form = _read(LOGIN_FORM)

    assert 'data-kaori-sso-actions' in form
    assert 'data-kaori-sso-provider-count="{{ sso_provider_rows|length }}"' in form
    assert 'data-kaori-sso-provider-grid' in form
    assert '{% if sso_provider_rows|length > 1 %}sm:grid-cols-2{% endif %}' in form
    assert 'data-kaori-sso-provider="{{ provider.provider_key }}"' in form
    assert 'class="inline-flex h-11 min-w-0 items-center justify-center' in form
    assert '<span class="min-w-0 truncate">{{ provider.display_name }}</span>' in form
    assert 'aria-label="Continue with {{ provider.display_name }}"' in form


def test_login_recomposes_across_canonical_device_classes() -> None:
    index = _read(INDEX)
    brand = _read(BRAND_PANEL)
    form = _read(LOGIN_FORM)
    css = _read(CSS)

    assert 'px-3 py-3 sm:px-5 sm:py-4 lg:px-6 lg:py-5' in index
    assert 'lg:grid-cols-12' in index

    assert 'relative hidden min-h-full' in brand
    assert 'lg:col-span-5' in brand
    assert 'lg:flex' in brand

    assert 'px-6 py-6 sm:px-8 lg:col-span-7 lg:px-10 xl:px-12' in form
    assert 'relative z-10 mx-auto w-full max-w-md' in form
    assert 'mb-6 flex items-center gap-3 lg:hidden' in form

    assert '{% if sso_provider_rows|length > 1 %}sm:grid-cols-2{% endif %}' in form
    assert 'h-11' in form
    assert 'w-full' in form

    assert '@media (min-width: 1024px)' in css
    assert '@media (max-height: 760px) and (min-width: 1024px)' in css
