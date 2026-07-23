from __future__ import annotations

from types import SimpleNamespace

from app.analytics.alerts import application
from app.analytics.alerts.contracts import normalize_page, normalize_per_page, paginate_items
from app.analytics.alerts.ownership import (
    extract_alert_contact_from_payload,
    extract_alert_owner_from_payload,
    extract_alert_runbook_from_payload,
)
from app.analytics.alerts.readiness import build_incident_readiness
from app.analytics.alerts.routing import build_routing_summary
from app.analytics.alerts.silences import silence_matches_alert
from app.analytics.alerts.sources import normalize_alertmanager_item, normalize_prometheus_alert


def test_filter_and_pagination_normalization_is_stable() -> None:
    assert normalize_page('0') == 1
    assert normalize_page('invalid') == 1
    assert normalize_per_page('25') == 25
    assert normalize_per_page('7') == 5

    rows, pagination = paginate_items(
        list(range(12)),
        page=2,
        per_page=5,
    )

    assert rows == [5, 6, 7, 8, 9]
    assert pagination.page == 2
    assert pagination.total_items == 12
    assert pagination.total_pages == 3
    assert pagination.start_item == 6
    assert pagination.end_item == 10
    assert pagination.has_prev is True
    assert pagination.has_next is True


def test_alertmanager_normalization_preserves_operational_metadata() -> None:
    normalized = normalize_alertmanager_item(
        {
            'labels': {
                'alertname': 'PodDown',
                'severity': 'Critical',
                'namespace': 'production',
                'pod': 'api-1',
                'team': 'platform',
                'contact': '#platform-oncall',
            },
            'annotations': {
                'summary': 'API pod is unavailable.',
                'description': 'The pod has not reported readiness.',
                'runbook_url': 'https://runbooks.example/pod-down',
            },
            'status': {
                'state': 'active',
                'silencedBy': ['silence-1'],
                'inhibitedBy': ['rule-1'],
            },
            'startsAt': '2026-07-23T01:02:03Z',
            'fingerprint': 'abc123',
            'receiver': 'pager',
        }
    )

    assert normalized['name'] == 'PodDown'
    assert normalized['severity'] == 'critical'
    assert normalized['status'] == 'active'
    assert normalized['namespace'] == 'production'
    assert normalized['target'] == 'api-1'
    assert normalized['source'] == 'Alertmanager'
    assert normalized['starts_at_display'] == '2026-07-23 01:02'
    assert normalized['owner'] == 'platform'
    assert normalized['runbook_url'] == 'https://runbooks.example/pod-down'
    assert normalized['contact'] == '#platform-oncall'
    assert normalized['silenced'] is True
    assert normalized['inhibited'] is True


def test_prometheus_normalization_preserves_fallback_shape() -> None:
    normalized = normalize_prometheus_alert(
        {
            'metric': {
                'alertname': 'HighCPU',
                'severity': 'Warning',
                'alertstate': 'firing',
                'namespace': 'production',
                'pod': 'api-2',
                'team': 'platform',
            },
            'value': [1721700000, '1'],
        }
    )

    assert normalized['name'] == 'HighCPU'
    assert normalized['severity'] == 'warning'
    assert normalized['status'] == 'firing'
    assert normalized['namespace'] == 'production'
    assert normalized['target'] == 'api-2'
    assert normalized['source'] == 'Prometheus'
    assert normalized['owner'] == 'platform'
    assert normalized['value'] == '1'


def test_routing_summary_keeps_group_and_receiver_counts() -> None:
    alerts = [
        {
            'name': 'HighCPU',
            'severity': 'critical',
            'namespace': 'production',
            'receiver': 'pager',
            'fingerprint': 'a',
            'labels': {
                'alertname': 'HighCPU',
                'namespace': 'production',
                'severity': 'critical',
                'job': 'api',
            },
        },
        {
            'name': 'HighCPU',
            'severity': 'warning',
            'namespace': 'production',
            'receiver': 'pager',
            'fingerprint': 'b',
            'labels': {
                'alertname': 'HighCPU',
                'namespace': 'production',
                'severity': 'warning',
                'job': 'api',
            },
        },
        {
            'name': 'PodDown',
            'severity': 'warning',
            'namespace': 'operations',
            'labels': {
                'alertname': 'PodDown',
                'namespace': 'operations',
                'severity': 'warning',
                'team': 'sre',
            },
        },
    ]

    summary = build_routing_summary(
        alerts=alerts,
        source_status={
            'resolved_source': 'alertmanager',
            'connected': True,
        },
    )

    assert summary['enabled'] is True
    assert summary['level'] == 'available'
    assert summary['alert_count'] == 3
    assert summary['receiver_count'] == 2
    assert summary['group_count'] == 3
    assert summary['fingerprint_count'] == 2
    assert summary['namespace_count'] == 2
    assert summary['receiver_groups'][0] == {
        'label': 'pager',
        'count': 2,
        'percent': 66.7,
    }


def test_silence_matching_keeps_equal_regex_and_negative_semantics() -> None:
    alert = {
        'labels': {
            'namespace': 'production',
            'alertname': 'HighCPU',
            'pod': 'api-7',
        }
    }

    assert silence_matches_alert(
        silence={
            'matchers': [
                {'name': 'namespace', 'value': 'production', 'isEqual': True, 'isRegex': False},
                {'name': 'pod', 'value': '^api-', 'isEqual': True, 'isRegex': True},
            ]
        },
        alert=alert,
    )
    assert not silence_matches_alert(
        silence={
            'matchers': [
                {'name': 'alertname', 'value': 'HighCPU', 'isEqual': False, 'isRegex': False},
            ]
        },
        alert=alert,
    )


def test_ownership_metadata_precedence_is_stable() -> None:
    assert (
        extract_alert_owner_from_payload(
            labels={'team': 'platform'},
            annotations={'owner': 'fallback-owner'},
            fallback_namespace='production',
        )
        == 'platform'
    )
    assert (
        extract_alert_owner_from_payload(
            labels={},
            annotations={},
            fallback_namespace='production',
        )
        == 'production'
    )
    assert (
        extract_alert_runbook_from_payload(
            annotations={'runbook_url': 'https://runbooks.example/high-cpu'},
        )
        == 'https://runbooks.example/high-cpu'
    )
    assert (
        extract_alert_contact_from_payload(
            labels={},
            annotations={'slack': '#platform-oncall'},
        )
        == '#platform-oncall'
    )


def test_incident_readiness_scoring_keeps_existing_penalty_model() -> None:
    readiness = build_incident_readiness(
        signal_overview={
            'critical_alerts': 1,
            'warning_alerts': 2,
            'anomalies': 1,
        },
        source_health={'score': 70},
        routing_summary={'enabled': False},
        silence_summary={'matched_alerts': 1},
        inhibition_summary={'matched_alerts': 1},
        ownership_summary={'score': 50},
    )

    assert readiness['score'] == 0
    assert readiness['level'] == 'incident_risk'
    assert readiness['routing_ready'] is False
    assert readiness['silence_risk'] == 1
    assert readiness['inhibition_risk'] == 1
    assert len(readiness['checks']) == 8


def test_application_context_keeps_page_contract(monkeypatch) -> None:
    cluster = SimpleNamespace(id=7)
    alert = {
        'name': 'HighCPU',
        'severity': 'critical',
        'status': 'firing',
        'namespace': 'production',
    }
    anomaly = {
        'name': 'Restart Spike',
        'severity': 'critical',
        'namespace': 'production',
    }
    source_status = {
        'configured': True,
        'connected': True,
        'resolved_source': 'alertmanager',
        'fallback_used': False,
    }

    monkeypatch.setattr(application, 'get_clusters_for_filter', lambda: [cluster])
    monkeypatch.setattr(application, 'get_selected_cluster', lambda **_: cluster)
    monkeypatch.setattr(application, 'get_namespace_options', lambda **_: ['production'])
    monkeypatch.setattr(application, 'load_alerts_by_source', lambda **_: ([alert], source_status))
    monkeypatch.setattr(application, 'load_prometheus_anomaly_metrics', lambda **_: [anomaly])
    monkeypatch.setattr(application, 'build_summary', lambda **_: {'total_alerts': 1})
    monkeypatch.setattr(
        application,
        'build_selected_cluster_signal_overview',
        lambda **_: {
            'critical_alerts': 1,
            'warning_alerts': 0,
            'anomalies': 1,
            'priority': {},
            'insight': {},
        },
    )
    monkeypatch.setattr(application, 'build_alerts_actionable_recommendations', lambda _: ['recommendation'])
    monkeypatch.setattr(application, 'format_recommendation_cards', lambda *_, **__: ['card'])
    monkeypatch.setattr(application, 'count_actionable_recommendations', lambda _: 1)
    monkeypatch.setattr(application, 'build_integration_status', lambda **_: {'ready': True})
    monkeypatch.setattr(application, 'build_source_health', lambda **_: {'score': 100})
    monkeypatch.setattr(application, 'build_routing_summary', lambda **_: {'enabled': True})
    monkeypatch.setattr(application, 'build_silence_summary', lambda **_: {'matched_alerts': 0})
    monkeypatch.setattr(application, 'build_inhibition_summary', lambda **_: {'matched_alerts': 0})
    monkeypatch.setattr(application, 'build_ownership_summary', lambda **_: {'score': 100})
    monkeypatch.setattr(application, 'build_incident_readiness', lambda **_: {'score': 100})
    monkeypatch.setattr(application, 'build_resource_links', lambda **_: {'alerts': '/alerts'})

    context = application.get_alerts_context(
        cluster_id='7',
        source='AUTO',
        severity='CRITICAL',
        status='FIRING',
        namespace='production',
        search='',
        page='1',
        alerts_per_page='5',
        anomalies_per_page='5',
    )

    assert context['selected_cluster'] is cluster
    assert context['selected_source'] == 'auto'
    assert context['selected_severity'] == 'critical'
    assert context['selected_status'] == 'firing'
    assert context['alerts'] == [alert]
    assert context['anomalies'] == [anomaly]
    assert context['recommendation_count'] == 1
    assert context['dependency_blocker'] is None
    assert context['resource_links'] == {'alerts': '/alerts'}
    assert context['alerts_pagination'].total_items == 1
