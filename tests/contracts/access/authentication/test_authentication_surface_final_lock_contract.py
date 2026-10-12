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
    assert 'Canonical Database Setup Workspace Composition' in lock
    assert 'console-first readiness workspace' in lock
    assert 'page title: 18 px (`text-lg`), semibold' in lock
    assert 'components/operational_flow_steps.html' in lock
    assert 'components/view_more_content.html' in lock
    assert 'components/terminal_command.html' in lock
    assert 'components/table_label.html' in lock


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

    prepaint_marker = 'data-kaori-prepaint-bootstrap="auth-theme"'
    stylesheet = "filename='css/output.css'"

    assert "filename='js/auth_login.js'" in layout
    assert layout.count(prepaint_marker) == 1
    assert layout.index(prepaint_marker) < layout.index(stylesheet)
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


def test_setup_bootstrap_neutral_copy_and_full_width() -> None:
    setup = read('app/templates/access/authentication/setup_required.html')
    lock = read('docs/design/KAORI_AUTHENTICATION_SURFACE_LOCK_V1.md')

    assert 'border-l-4 border-kaori-primary' not in setup
    assert '<div class="px-4 py-4 sm:px-5">' in setup
    assert 'text-content-secondary">Primary action · One-time setup' in setup
    assert '<div class="space-y-5">' in setup
    assert 'lg:grid-cols-2' not in setup
    assert "label='Manual Bootstrap'" in setup
    assert (
        'Run once in Windows PowerShell at the repo root to create the '
        'schema, grants, and admin.'
    ) in setup
    assert 'Preserve INTEGRATION_CREDENTIAL_KEY.' in setup
    assert 'Create schema, grants, and admin.' in setup
    assert (
        'Use the host terminal; never migrate with the runtime DATABASE_URL.'
        in setup
    )
    assert 'no Violet left-edge stripe' in lock
    assert 'full-width Manual Bootstrap command' in lock



def test_setup_production_is_operator_guidance_without_public_migration_commands() -> None:
    setup = read('app/templates/access/authentication/setup_required.html')
    lock = read('docs/design/KAORI_AUTHENTICATION_SURFACE_LOCK_V1.md')

    assert 'data-kaori-setup-production-guidance' in setup
    assert 'Complete Authorized Database Initialization' in setup
    assert 'Database Connection Unavailable' in setup
    assert 'Application initialization is pending.' in setup
    assert 'Contact your deployment administrator.' in setup
    assert 'bash scripts/init_db.sh --bootstrap-admin' not in setup
    assert 'flask --app run:app db upgrade' not in setup
    assert 'flask --app run:app seed-rbac' not in setup
    assert 'Production/non-development' in lock
    assert 'never exposes migration commands' in lock


def test_setup_devcontainer_commands_are_environment_gated() -> None:
    setup = read('app/templates/access/authentication/setup_required.html')
    source_start = setup.index('{% set devcontainer_setup =')
    first_guard = setup.index('{% if devcontainer_setup %}', source_start)
    first_guard_end = setup.index('{% endif %}', first_guard)
    dev_context = setup[first_guard:first_guard_end]

    assert 'APP_ENV' in setup[source_start:first_guard]
    assert "not config.get('TESTING', false)" in setup[source_start:first_guard]
    assert 'run --rm db-bootstrap' in dev_context
    assert 'pg_isready -h db -p 5432' in dev_context
    assert 'INTEGRATION_CREDENTIAL_KEY' in dev_context
    assert 'data-kaori-setup-production-guidance' in setup
    assert '{% if readiness.setup_required %}' in setup
    assert 'This readiness workspace is read-only.' in setup
