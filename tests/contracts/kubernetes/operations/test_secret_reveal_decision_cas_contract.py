from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_reveal_decision_serializes_postgres_and_checks_atomic_transition() -> None:
    service = (ROOT / 'app/kubernetes/operations/secrets/reveal_service.py').read_text()
    decision = service.split('def decide_reveal_request(', 1)[1].split(
        '\ndef get_reveal_request_for_user(', 1
    )[0]
    assert ".enable_eagerloads(False)" in decision
    assert ".with_for_update(of=SecretRevealRequest)" in decision
    assert "SecretRevealRequest.status == 'pending'" in decision
    assert "SecretRevealRequest.expires_at > now" in decision
    assert "synchronize_session=False" in decision
    assert "if changed != 1:" in decision
    assert "db.session.rollback()" in decision
    assert "db.session.commit()" in decision
    assert "db.session.refresh(record)" in decision
