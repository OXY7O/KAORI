from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'partials'
CSS = ROOT / 'app' / 'static' / 'css' / 'auth-login.css'
FABRIC = ROOT / 'app' / 'static' / 'images' / 'kaori-login-operations-fabric.svg'
LOGIN_FORM = TEMPLATES / '_login_form.html'


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
