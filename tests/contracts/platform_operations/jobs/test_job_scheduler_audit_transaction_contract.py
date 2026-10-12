from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_automatic_queue_audit_and_policy_outcome_share_a_transaction() -> None:
    scheduler = (ROOT / 'app/platform_operations/jobs/scheduler.py').read_text(encoding='utf-8')
    successful_dispatch = scheduler.split('if outcome.job is not None and outcome.created:', 1)[1]
    assert 'commit=False' in successful_dispatch
    assert 'current.last_dispatch_status = outcome.status' in successful_dispatch
    assert 'db.session.commit()' in successful_dispatch
    assert 'except SQLAlchemyError:' in successful_dispatch


def test_post_dispatch_evidence_failure_does_not_enqueue_again() -> None:
    scheduler = (ROOT / 'app/platform_operations/jobs/scheduler.py').read_text(encoding='utf-8')
    error_branch = scheduler.split('except SQLAlchemyError:', 1)[1]
    assert "current.last_dispatch_status = 'evidence_failed'" in error_branch
    assert " 'status': 'evidence_failed'" in error_branch
    assert "logger.exception('Could not persist degraded dispatch evidence" in error_branch
    assert "dispatch_registered_job(" not in error_branch
    assert 'continue' in error_branch
