from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_session_admission_is_shared_by_credentials_sso_and_existing_sessions() -> None:
    admission = read('app/access/authentication/admission.py')
    services = read('app/access/authentication/services.py')
    routes = read('app/access/authentication/routes.py')
    login_extension = read('app/extensions/login.py')

    assert 'def session_admission_reason(' in admission
    assert 'if not user.is_active:' in admission
    assert 'if user.is_super_admin:' in admission
    assert "normalized_source != 'database'" in admission
    assert 'if account_source != normalized_source:' in admission
    assert 'if role is None or not role.is_active:' in admission

    assert 'enforce_login_admission(result)' in services
    assert 'enforce_login_admission(resolve_sso_identity(provider, identity))' in routes
    assert 'session_admission_reason(user, source=source)' in login_extension


def test_credential_failures_do_not_expose_account_provider_or_role_state() -> None:
    services = read('app/access/authentication/services.py')
    routes = read('app/access/authentication/routes.py')
    results = read('app/access/authentication/results.py')

    assert 'def credential_failure_message(' in services
    assert "if result.reason == 'database_unavailable':" in services
    assert 'return INVALID_LOGIN_MESSAGE' in services
    assert 'message = credential_failure_message(result)' in routes
    assert "'access_not_permitted'" in results

    login_block = routes.split('def login():', 1)[1].split("@auth_bp.get('/sso/", 1)[0]
    assert 'PROVIDER_UNAVAILABLE_MESSAGE' not in login_block
    assert 'USER_INACTIVE_MESSAGE' not in login_block


def test_post_login_redirects_accept_only_internal_absolute_paths() -> None:
    session_source = read('app/access/authentication/session.py')
    routes = read('app/access/authentication/routes.py')
    forms = read('app/access/authentication/forms.py')
    template = read('app/templates/access/authentication/partials/_login_form.html')

    assert 'def safe_next_url(' in session_source
    assert "not candidate.startswith('/')" in session_source
    assert "candidate.startswith('//')" in session_source
    assert "if '\\\\' in candidate" in session_source
    assert 'parsed.scheme or parsed.netloc' in session_source

    assert 'next = HiddenField()' in forms
    assert "form.next.data = safe_next_url(request.args.get('next')) or ''" in routes
    assert "'next_url': safe_next_url(request.args.get('next'))" in routes
    assert "next_url=flow.get('next_url')" in routes
    assert 'provider_login_url' in template
    assert 'next=form.next.data' in template


def test_logout_and_revocation_clear_persistent_remember_cookie() -> None:
    session_source = read('app/access/authentication/session.py')
    login_extension = read('app/extensions/login.py')
    routes = read('app/access/authentication/routes.py')

    assert "remember_instruction = session.get('_remember')" in session_source
    assert "session['_remember'] = 'clear'" in session_source
    assert "session['_remember'] = 'clear'" in login_extension
    assert 'logout_user()' in routes
    assert 'clear_authenticated_session()' in routes


def test_remember_me_window_is_bounded_for_infrastructure_access() -> None:
    config = read('app/config/default.py')
    env_example = read('.env.example')
    production_app = read('deploy/env/app.env.example')

    assert 'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(' in config
    assert "'AUTH_REMEMBER_ME_DAYS'," in config
    assert 'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)' in config
    assert 'AUTH_REMEMBER_ME_DAYS=7' in env_example
    assert 'AUTH_REMEMBER_ME_DAYS=7' in production_app


def test_authentication_rate_limits_are_audited() -> None:
    limiter = read('app/extensions/limiter.py')

    assert "source='credentials'" in limiter
    assert "source='sso'" in limiter
    assert "reason='rate_limited'" in limiter
    assert 'record_authentication_activity(' in limiter


def test_login_form_bounds_untrusted_credential_input() -> None:
    forms = read('app/access/authentication/forms.py')
    results = read('app/access/authentication/results.py')

    assert "username = StringField('Username', validators=[DataRequired(), Length(max=100)])" in forms
    assert "password = PasswordField('Password', validators=[DataRequired(), Length(max=1024)])" in forms
    assert 'Please check the database connection' not in results
    assert 'Sign-in service is temporarily unavailable.' in results
