from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / 'app' / 'auth' / 'audit.py'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_authentication_audit_uses_v2_actor_and_target_semantics() -> None:
    source = AUDIT.read_text(encoding='utf-8')

    assert "AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v2'" in source
    assert "'target_user_id': user.id if user is not None else None" in source
    assert "'actor_authenticated': authenticated_actor is not None" in source
    assert "'actor_user_id': authenticated_actor.id if authenticated_actor is not None else None" in source
    assert 'authenticated_actor = user if user is not None and (success or is_logout) else None' in source


def test_failed_attempts_do_not_claim_authenticated_actor_identity() -> None:
    source = AUDIT.read_text(encoding='utf-8')

    for field in ('actor_display_name', 'actor_email', 'actor_role'):
        assert f"'{field}': authenticated_actor." in source
    assert 'Keep failed attempts linked to a resolved target account' in source


def test_authentication_audit_bounds_untrusted_request_metadata() -> None:
    source = AUDIT.read_text(encoding='utf-8')

    assert 'def _bounded_text(' in source
    assert '_bounded_text(username, limit=255)' in source
    assert "_bounded_text(request.headers.get('User-Agent'), limit=1024)" in source
    assert '_bounded_text(request.remote_addr, limit=100)' in source
    assert "'request_path': _bounded_text(request.path, limit=500)" in source
    assert "'request_endpoint': _bounded_text(request.endpoint, limit=160)" in source

    # The callback query string can contain an authorization code. Audit must
    # persist request.path only and never request.url/full_path/query_string.
    assert 'request.query_string' not in source
    assert 'request.full_path' not in source
    assert 'request.url' not in source


def test_authentication_audit_has_security_reason_codes_without_secret_payloads() -> None:
    audit = AUDIT.read_text(encoding='utf-8')
    results = read('app/auth/results.py')

    assert "'access_not_permitted'" in audit
    assert "'rate_limited'" in audit
    assert "'access_not_permitted'" in results
    assert "'rate_limited'" in results

    metadata_block = audit.split('activity.metadata_json = {', 1)[1].split('}', 1)[0].lower()
    for forbidden in ('password', 'authorization_code', 'access_token', 'id_token', 'client_secret'):
        assert f"'{forbidden}'" not in metadata_block


def test_activity_presentation_does_not_render_failed_target_account_as_actor() -> None:
    presentation = read('app/notifications/presentation.py')
    queries = read('app/notifications/queries.py')

    assert "notification.event_type == 'authentication'" in presentation
    assert "str(metadata.get('result') or '').strip().lower() == 'failed'" in presentation
    assert "user_label = 'Unauthenticated Request'" in presentation
    assert "actor_role = 'No Authenticated Role'" in presentation
    assert 'if unauthenticated_attempt' in presentation

    # The Activity Register actor filter and 24h actor KPI must exclude a user
    # that was merely targeted by a failed authentication attempt.
    assert "Notification.event_type != 'authentication'" in queries
    assert "Notification.status == 'success'" in queries
    assert 'actor_identity = case(' in queries
    assert "Notification.status != 'success'" in queries
    assert 'func.count(func.distinct(actor_identity))' in queries



def test_account_authentication_audit_links_use_supported_access_filters() -> None:
    recent = read("app/templates/settings/account/partials/_recent_login_activity.html")
    privacy = read("app/templates/settings/account/partials/_activity_information.html")

    for source in (recent, privacy):
        assert "category='access'" in source
        assert "search=current_user.username" in source
        assert "event_type='authentication'" not in source
