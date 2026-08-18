from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_authentication_surface_final_lock_is_release_gated_and_documented() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    readme = read('app/access/authentication/README.md')
    lock = read('docs/design/KAORI_AUTHENTICATION_SURFACE_LOCK_V1.md')

    assert 'python scripts/verify_authentication_surface_final_lock.py' in quality_gate
    assert 'Authentication Surface v1 is final-locked' in readme
    assert 'Status: **FINAL LOCKED**' in lock
    assert 'Login' in lock
    assert 'Database Setup Required' in lock


def test_authentication_presentation_uses_canonical_typography_and_external_runtime() -> None:
    auth_templates = sorted((ROOT / 'app/templates/access/authentication').rglob('*.html'))
    layout = read('app/templates/layouts/auth.html')

    assert auth_templates
    for path in auth_templates:
        source = path.read_text(encoding='utf-8')
        assert 'text-[' not in source
        assert 'tracking-[' not in source
        assert 'font-extrabold' not in source
        assert ' uppercase ' not in f' {source} '

    assert "filename='js/auth_login.js'" in layout
    assert layout.count('<script>') == 1
    assert "localStorage.getItem('theme')" in layout


def test_authentication_security_and_compact_login_contract_remain_locked() -> None:
    routes = read('app/access/authentication/routes.py')
    session_source = read('app/access/authentication/session.py')
    login = read('app/templates/access/authentication/partials/_login_form.html')
    css = read('app/static/css/auth-login.css')

    assert "@auth_bp.route('/login', methods=['GET', 'POST'])" in routes
    assert "@auth_bp.route('/logout', methods=['POST'])" in routes
    assert 'def safe_next_url(' in session_source
    assert "current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)" in session_source
    assert 'form.hidden_tag()' in login
    assert 'width: min(1060px, 100%);' in css
    assert 'height: 44px;' in css
    assert '@media (max-height: 760px) and (min-width: 1024px)' in css
