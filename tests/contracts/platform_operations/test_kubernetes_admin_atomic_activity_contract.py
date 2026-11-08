"""Privileged Kubernetes Admin mutation and Activity Audit share a DB transaction."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_protected_policy_mutation_defers_commit_until_audit_staged() -> None:
    policy = (ROOT / 'app/kubernetes/operations/secrets/reveal_policy.py').read_text()
    routes = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    service = (ROOT / 'app/platform_operations/notifications/service.py').read_text()
    secret_service = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/service.py').read_text()
    writer = (ROOT / 'app/platform_operations/notifications/writer.py').read_text()
    assert policy.count('commit: bool = True') >= 2
    assert routes.count('commit=False') == 2
    assert routes.count('durable_with_operation=True') == 2
    assert routes.count('commit_secret_reveal_settings_transaction()') == 2
    commit = secret_service.split('def commit_secret_reveal_settings_transaction() -> None:', 1)[1]
    commit = commit.split('\ndef ', 1)[0]
    assert 'db.session.commit()' in commit
    assert 'db.session.commit()' not in routes
    writer_selection = routes.split('def _record_settings_activity(', 1)[1]
    writer_selection = writer_selection.split('@bp.route', 1)[0]
    assert 'if durable_with_operation:' in writer_selection
    assert 'return stage_operational_activity(' in writer_selection
    assert 'return record_operational_activity(' in writer_selection
    staged = writer_selection.index('return stage_operational_activity(')
    non_durable = writer_selection.index('return record_operational_activity(')
    assert staged < non_durable
    assert 'def stage_operational_activity(' in service
    assert 'commit=False' in service.split('def stage_operational_activity(', 1)[1]
    assert 'if commit:' in writer
    assert 'db.session.add(notification)' in writer


def test_atomic_evidence_failure_cannot_silently_downgrade_to_best_effort() -> None:
    service = (ROOT / 'app/platform_operations/notifications/service.py').read_text()
    block = service.split('def stage_operational_activity(', 1)[1]
    assert 'except Exception' not in block
    assert 'persist_notification(' in block
