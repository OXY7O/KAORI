from __future__ import annotations

from types import SimpleNamespace

from app.platform_operations.jobs import configuration
from app.platform_operations.overview import presentation


def test_configuration_dispatch_attention_is_read_only(monkeypatch):
    statuses = []
    calls = []

    class Query:
        def filter(self, *args):
            calls.append(args)
            return self

        def count(self):
            return 2

    monkeypatch.setattr(
        configuration,
        'JobPolicy',
        SimpleNamespace(
            query=Query(),
            last_dispatch_status=SimpleNamespace(in_=lambda values: statuses.append(set(values)) or 'matching'),
        ),
    )
    assert configuration.build_job_configuration_attention_summary() == 2
    assert statuses == [{'failed', 'partially_succeeded', 'evidence_failed'}]
    assert calls == [('matching',)]


def test_overview_warns_on_dispatch_failure_without_execution(monkeypatch):
    monkeypatch.setattr(
        presentation,
        'build_job_execution_status_context',
        lambda: {'job_stats': {'attention': 0, 'active': 0, 'completed_24h': 0}},
    )
    monkeypatch.setattr(presentation, 'build_job_configuration_attention_summary', lambda: 1)

    context = presentation.build_platform_operations_overview_context(
        can_jobs=True, can_data_lifecycle=False, can_kubernetes_admin=False
    )

    assert context['workspaces'][0]['status_label'] == 'Needs Attention'
    assert context['workspaces'][0]['status_tone'] == 'warning'
    assert context['workspaces'][0]['metrics'][1] == ('triangle-alert', 'Execution / Policy Alerts', '0 / 1')
    assert context['review_workspace_count'] == 1
    assert context['workspaces'][0]['action_endpoint'] == 'jobs.configuration'
    assert context['workspaces'][0]['action_label'] == 'Review Job Configuration'


def test_overview_does_not_query_jobs_for_unauthorized_user(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('No job projection may run without jobs.view')

    monkeypatch.setattr(presentation, 'build_job_execution_status_context', forbidden)
    monkeypatch.setattr(presentation, 'build_job_configuration_attention_summary', forbidden)
    context = presentation.build_platform_operations_overview_context(
        can_jobs=False, can_data_lifecycle=False, can_kubernetes_admin=False
    )
    assert context['workspaces'] == []


def test_execution_attention_keeps_canonical_executions_handoff(monkeypatch):
    monkeypatch.setattr(
        presentation,
        'build_job_execution_status_context',
        lambda: {'job_stats': {'attention': 1, 'active': 0, 'completed_24h': 0}},
    )
    monkeypatch.setattr(presentation, 'build_job_configuration_attention_summary', lambda: 1)

    context = presentation.build_platform_operations_overview_context(
        can_jobs=True, can_data_lifecycle=False, can_kubernetes_admin=False
    )
    assert context['workspaces'][0]['action_endpoint'] == 'jobs.executions'
    assert context['workspaces'][0]['action_label'] == 'Open Jobs & Executions'
