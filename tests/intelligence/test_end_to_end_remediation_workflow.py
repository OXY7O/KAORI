from types import SimpleNamespace

from app.knowledge import remediation_workflow as workflow


class Candidate:
    executable = False


def test_alert_intake_matches_then_persists_non_executable_candidate(monkeypatch):
    calls = []
    persisted = SimpleNamespace(public_id='candidate-1')

    monkeypatch.setattr(
        workflow, 'match_alert_to_runbook', lambda alert, bindings: calls.append('match') or Candidate()
    )
    monkeypatch.setattr(workflow, 'persist_candidate', lambda candidate, **kwargs: calls.append('persist') or persisted)

    result = workflow.ingest_alert_for_review(
        {'labels': {'alertname': 'KubePodNotReady'}},
        bindings=[],
        severity='critical',
        actor_user_id=1,
        actor_permissions={'intelligence.decisions.view'},
    )

    assert result.candidate is persisted
    assert calls == ['match', 'persist']


def test_approve_and_enqueue_orders_approval_authorization_delivery(monkeypatch):
    calls = []
    decision = SimpleNamespace(workflow_status='pending_approval')
    journal = SimpleNamespace(public_id='journal-1')
    job = SimpleNamespace(id=7)

    def approve(record, **kwargs):
        calls.append('approve')
        record.workflow_status = 'approved'

    monkeypatch.setattr(workflow, 'approve_decision', approve)
    monkeypatch.setattr(
        workflow,
        'issue_persisted_execution_token',
        lambda record, **kwargs: calls.append('authorize') or ('token', journal),
    )
    monkeypatch.setattr(
        workflow,
        'enqueue_execution_delivery',
        lambda record, **kwargs: calls.append('enqueue') or (job, True),
    )

    result = workflow.approve_and_enqueue_decision(
        decision,
        task=object(),
        secret_key='secret',
        actor_user_id=1,
        actor_permissions={
            'intelligence.decisions.approve',
            'intelligence.decisions.execute',
        },
    )

    assert result.journal is journal
    assert result.job is job
    assert result.created is True
    assert calls == ['approve', 'authorize', 'enqueue']


def test_non_reviewable_decision_never_issues_authorization(monkeypatch):
    decision = SimpleNamespace(workflow_status='dispatched')
    called = False

    def issue(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(workflow, 'issue_persisted_execution_token', issue)

    try:
        workflow.approve_and_enqueue_decision(
            decision,
            task=object(),
            secret_key='secret',
            actor_user_id=1,
            actor_permissions={'intelligence.decisions.execute'},
        )
    except workflow.RemediationWorkflowError:
        pass
    else:
        raise AssertionError('Expected fail-closed workflow error.')

    assert called is False
