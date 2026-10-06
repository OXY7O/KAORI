from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / 'app' / 'access' / 'authentication' / 'audit.py'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_authentication_audit_uses_immutable_actor_and_target_semantics() -> None:
    source = AUDIT.read_text(encoding='utf-8')

    assert "AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v2'" in source
    assert "'target_user_id': user.id if user is not None else None" in source
    assert 'authenticated_actor = user if user is not None and (success or is_logout) else None' in source
    assert 'actor_snapshot_for_user(authenticated_actor)' in source
    assert 'unauthenticated_actor_snapshot()' in source
    assert 'activity.actor_snapshot_json = actor.as_json()' in source
    assert 'activity.actor_key = actor.key' in source
    assert 'activity.actor_label = actor.label' in source


def test_failed_attempts_do_not_claim_target_account_as_actor() -> None:
    source = AUDIT.read_text(encoding='utf-8')
    actors = read('app/platform_operations/notifications/actors.py')

    assert 'else unauthenticated_actor_snapshot()' in source
    assert "key='unauthenticated'" in actors
    assert "label='Unauthenticated Request'" in actors
    assert "role='No Authenticated Role'" in actors
    assert 'Keep failed attempts linked to a resolved target account' in source


def test_authentication_audit_is_hidden_from_personal_notification_center() -> None:
    source = AUDIT.read_text(encoding='utf-8')
    assert 'activity.deck_visible = False' in source
    assert 'activity.read_at = created_at' in source


def test_authentication_audit_bounds_untrusted_request_metadata() -> None:
    source = AUDIT.read_text(encoding='utf-8')

    assert 'def _bounded_text(' in source
    assert '_bounded_text(username, limit=255)' in source
    assert "_bounded_text(request.headers.get('User-Agent'), limit=1024)" in source
    assert '_bounded_text(request.remote_addr, limit=100)' in source
    assert "'request_path': _bounded_text(request.path, limit=500)" in source
    assert "'request_endpoint': _bounded_text(request.endpoint, limit=160)" in source
    assert 'request.query_string' not in source
    assert 'request.full_path' not in source
    assert 'request.url' not in source


def test_authentication_audit_has_security_reason_codes_without_secret_payloads() -> None:
    audit = AUDIT.read_text(encoding='utf-8')
    results = read('app/access/authentication/results.py')

    assert "'access_not_permitted'" in audit
    assert "'rate_limited'" in audit
    assert "'access_not_permitted'" in results
    assert "'rate_limited'" in results

    metadata_block = audit.split('activity.metadata_json = {', 1)[1].split('}', 1)[0].lower()
    for forbidden in ('password', 'authorization_code', 'access_token', 'id_token', 'client_secret'):
        assert f"'{forbidden}'" not in metadata_block


def test_activity_presentation_uses_snapshot_instead_of_live_target_user_identity() -> None:
    presentation = read('app/platform_operations/notifications/presentation.py')
    queries = read('app/platform_operations/notifications/queries.py')

    assert 'actor_snapshot = notification.actor_snapshot_json or {}' in presentation
    assert 'notification.actor_label' in presentation
    assert 'user.role_display_name' not in presentation.split('def _serialize_notification(', 1)[1]
    assert 'Notification.actor_key == normalized_actor_key' in queries
    assert 'func.count(func.distinct(Notification.actor_key))' in queries
    activity_query = queries.split('def get_notification_activity_context(', 1)[1].split(
        'def mark_notification_read(', 1
    )[0]
    assert 'User.id == Notification.user_id' not in activity_query


def test_account_authentication_audit_links_use_supported_access_filters() -> None:
    recent = read('app/templates/settings/account/partials/_recent_login_activity.html')

    assert not (ROOT / 'app/templates/settings/account/partials/_activity_information.html').exists()
    assert "category='access'" in recent
    assert 'search=current_user.username' in recent
    assert "event_type='authentication'" not in recent
