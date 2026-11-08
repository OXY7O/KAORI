from datetime import UTC, datetime
from types import SimpleNamespace

from app.reports.export.payloads import artifact_registry_analysis as module


def test_registry_report_collects_committed_sections_not_fast_shell(monkeypatch) -> None:
    instance = SimpleNamespace(id=7, name='registry-uat', provider_key='harbor', environment='uat')
    seen: list[tuple[str, int]] = []

    def section(name: str, *, provider_id: int) -> dict:
        seen.append((name, provider_id))
        return {
            'overview': {
                'project_count': 3,
                'repository_count': 4,
                'artifact_count': 8,
                'total_size': '20 MiB',
                'scanned_count': 5,
                'scan_coverage': 62,
                'critical_findings': 2,
                'high_findings': 1,
                'posture': {'label': 'Attention Required'},
            },
            'capacity': {
                'capacity': {'growth': {'size_growth_display': '2 MiB/day'}},
                'forecast': {'status': 'Ready'},
                'top_consumers': [{'project_name': 'app', 'usage_display': '10 MiB'}],
            },
            'signals': {
                'alerts': {
                    'critical': 1,
                    'warning': 0,
                    'info': 0,
                    'total': 1,
                    'rows': [{'title': 'Registry pressure', 'severity': 'critical'}],
                },
                'recommended_actions': [{'title': 'Review quota'}],
            },
        }[name]

    monkeypatch.setattr(module, 'validate_report_instance', lambda report: None)
    monkeypatch.setattr(module, '_resolve_registry_instance', lambda report: (7, instance, None))
    monkeypatch.setattr(
        module,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                get=lambda model, pk: SimpleNamespace(last_committed_at=datetime(2026, 10, 12, tzinfo=UTC))
            )
        ),
    )
    monkeypatch.setattr(module, 'build_overview_section', section)
    monkeypatch.setattr(module, '_query_artifacts', lambda instance_id: [])
    monkeypatch.setattr(module, '_governance_payload', lambda instance_id: {'collection_status': 'ready'})
    monkeypatch.setattr(module, '_runtime_payload', lambda instance_id, overview: {'bindings': 2})

    result = module.get_report_artifact_registry_analysis_payload(SimpleNamespace())

    assert seen == [('overview', 7), ('capacity', 7), ('signals', 7)]
    assert result['summary']['projects'] == 3
    assert result['summary']['repositories'] == 4
    assert result['summary']['artifacts'] == 8
    assert result['artifact_registry_capacity_usage']['forecast']['status'] == 'Ready'
    assert len(result['top_consumers']) == 1
    assert result['artifact_registry_alerts_actions']['summary']['critical'] == 1
    assert result['recommendations'][0]['title'] == 'Review quota'


def test_registry_report_rejects_uncommitted_inventory(monkeypatch) -> None:
    monkeypatch.setattr(module, 'validate_report_instance', lambda report: None)
    monkeypatch.setattr(
        module,
        '_resolve_registry_instance',
        lambda report: (7, SimpleNamespace(id=7), None),
    )
    monkeypatch.setattr(
        module,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda model, pk: None)),
    )
    result = module.get_report_artifact_registry_analysis_payload(SimpleNamespace())
    assert result == {'_error': 'Selected Artifact Registry has no committed inventory evidence.'}
