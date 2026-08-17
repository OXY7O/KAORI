from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]


def _load_records_module():
    names = [
        'app',
        'app.analytics',
        'app.kubernetes.analytics.alerts',
        'app.kubernetes.analytics.alerts.contracts',
        'app.kubernetes.analytics.alerts.metrics',
        'app.kubernetes.analytics.alerts.ownership',
    ]
    previous = {name: sys.modules.get(name) for name in names}
    try:
        for package in names[:3]:
            sys.modules[package] = ModuleType(package)

        contracts = ModuleType('app.kubernetes.analytics.alerts.contracts')
        contracts.NormalizedAlert = dict
        sys.modules[contracts.__name__] = contracts

        metrics = ModuleType('app.kubernetes.analytics.alerts.metrics')
        metrics.get_metric_labels = lambda item: dict(item.get('metric') or {})
        sys.modules[metrics.__name__] = metrics

        ownership = ModuleType('app.kubernetes.analytics.alerts.ownership')
        ownership.extract_alert_contact_from_payload = lambda **_: ''
        ownership.extract_alert_owner_from_payload = lambda **_: 'Unassigned'
        ownership.extract_alert_runbook_from_payload = lambda **_: ''
        sys.modules[ownership.__name__] = ownership

        spec = importlib.util.spec_from_file_location(
            'alerts_records_under_test',
            ROOT / 'app/kubernetes/analytics/alerts/records.py',
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def test_metrics_source_replica_records_are_deduplicated() -> None:
    records = _load_records_module()
    first = records.normalize_metrics_source_alert(
        {
            'metric': {
                'alertname': 'HighErrorRate',
                'severity': 'warning',
                'namespace': 'payments',
                'service': 'api',
                'prometheus_replica': 'prometheus-0',
            },
            'value': [0, '1'],
        }
    )
    second = records.normalize_metrics_source_alert(
        {
            'metric': {
                'alertname': 'HighErrorRate',
                'severity': 'warning',
                'namespace': 'payments',
                'service': 'api',
                'prometheus_replica': 'prometheus-1',
            },
            'value': [0, '1'],
        }
    )

    assert len(records.deduplicate_alerts([first, second])) == 1


def test_namespace_filter_is_exact_and_severity_is_canonical() -> None:
    records = _load_records_module()
    assert records.normalize_severity('P1') == 'critical'
    assert records.normalize_severity('warn') == 'warning'

    items = [
        {'namespace': 'prod', 'severity': 'warning', 'status': 'firing'},
        {'namespace': 'prod-canary', 'severity': 'warning', 'status': 'firing'},
    ]
    filtered = records.filter_items(
        items,
        severity='all',
        status='all',
        namespace='prod',
        search='',
    )
    assert filtered == [items[0]]


def test_pending_and_firing_metrics_source_copies_collapse_to_firing() -> None:
    records = _load_records_module()
    pending = {
        'source': 'Metrics Source',
        'name': 'HighLatency',
        'namespace': 'payments',
        'target': 'api-1',
        'severity': 'warning',
        'status': 'pending',
        'labels': {
            'alertname': 'HighLatency',
            'namespace': 'payments',
            'pod': 'api-1',
            'alertstate': 'pending',
        },
    }
    firing = {
        **pending,
        'status': 'firing',
        'labels': {**pending['labels'], 'alertstate': 'firing'},
    }

    rows = records.deduplicate_alerts([pending, firing])

    assert len(rows) == 1
    assert rows[0]['status'] == 'firing'
