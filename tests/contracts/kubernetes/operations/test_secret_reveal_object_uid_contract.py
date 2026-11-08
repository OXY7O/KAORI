from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_request_commits_live_secret_uid_without_plaintext() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    model = read('app/models/secret_reveal.py')
    assert 'secret_uid: Mapped[str | None]' in model
    assert "secret_uid = str(target.uid or '').strip()" in service
    assert 'record.secret_uid = secret_uid' in service
    assert 'if not secret_uid:' in service


def test_approval_and_reveal_reject_recreated_secret_object() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    assert "live_target.uid or ''" in service
    assert 'live_target.secret_type != record.secret_type' in service
    assert 'live_uid != approved_uid' in service
    assert 'live_secret_type != record.secret_type' in service
    assert 'scrub_secret_payload(secret_object)' in service
    assert 'with_for_update(of=SecretRevealRequest)' in service


def test_legacy_requests_are_fail_closed_at_schema_admission() -> None:
    migration = read('migrations/versions/20261011_secret_reveal_object_uid.py')
    assert "revision = '20261011_reveal_uid'" in migration
    assert 'secret_uid IS NULL' in migration
    assert "status = 'expired'" in migration
