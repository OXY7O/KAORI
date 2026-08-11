from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_access_final_lock_is_release_gated_and_documented() -> None:
    lock = read('docs/design/KAORI_ACCESS_LOCK_V1.md')
    ownership = read('docs/architecture/ACCESS_OWNERSHIP.md')
    quality_gate = read('scripts/quality_gate.sh')
    verifier = read('scripts/verify_access_final_lock.py')

    assert 'Final Locked — Access v1' in ownership
    assert 'KAORI Access Final Lock v1' in lock
    assert 'python scripts/verify_access_final_lock.py' in quality_gate
    assert "print(f'PASS — KAORI Access Final Lock v1 · {len(templates)} templates')" in verifier
    assert "print('FAIL — KAORI Access Final Lock v1')" in verifier


def test_access_final_lock_preserves_authentication_actor_and_session_security() -> None:
    config = read('app/config/default.py')
    queries = read('app/notifications/queries.py')
    session = read('app/auth/session.py')

    assert 'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(' in config
    assert "'AUTH_REMEMBER_ME_DAYS'," in config
    assert 'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)' in config
    assert "current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)" in session

    assert 'actor_identity = case(' in queries
    assert "Notification.event_type == 'authentication'" in queries
    assert "Notification.status != 'success'" in queries
    assert 'func.count(func.distinct(actor_identity))' in queries
    assert "Notification.event_type != 'authentication'" in queries
    assert "Notification.status == 'success'" in queries


def test_access_final_lock_protects_content_driven_modal_formatter_boundary() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')

    assert 'h-auto max-h-[calc(100dvh-1rem)]' in modal
    assert 'max-h-[calc(100dvh-1rem) ]' not in modal
    djlint_off = modal.find('{# djlint:off #}')
    dialog_open = modal.find('<section id="{{ dialog_id }}"')
    dialog_close = modal.find('</section>', dialog_open)
    djlint_on = modal.find('{# djlint:on #}')

    assert 0 <= djlint_off < dialog_open < dialog_close < djlint_on


def test_current_access_documents_do_not_reopen_the_locked_ui() -> None:
    current_docs = (
        read('app/access/README.md'),
        read('app/users/README.md'),
        read('docs/architecture/ACCESS_OWNERSHIP.md'),
        read('docs/design/KAORI_ACCESS_LOCK_V1.md'),
    )

    for document in current_docs:
        assert 'UI not final locked' not in document
        assert 'not final-lock the UI' not in document
