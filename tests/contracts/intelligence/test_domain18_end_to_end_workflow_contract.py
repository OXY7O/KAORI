from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / 'app/knowledge/remediation_workflow.py'
TASKS = ROOT / 'app/resolver/tasks.py'


def test_workflow_keeps_alert_candidate_and_execution_boundaries_separate():
    text = WORKFLOW.read_text()
    assert 'match_alert_to_runbook' in text
    assert 'persist_candidate' in text
    assert 'promote_candidate' in text
    assert 'issue_persisted_execution_token' in text
    assert 'enqueue_execution_delivery' in text
    assert 'dispatch_resolver_execution' not in text


def test_worker_owns_resolver_dispatch_under_a_lease():
    text = TASKS.read_text()
    assert 'acquire_execution_lease' in text
    assert 'dispatch_resolver_execution' in text
    assert 'complete_execution_delivery' in text
    assert "name='app.resolver.tasks.execute_authorized_resolution'" in text


def test_domain18_does_not_add_a_database_migration():
    migrations = list((ROOT / 'migrations/versions').glob('*end_to_end*'))
    assert migrations == []
