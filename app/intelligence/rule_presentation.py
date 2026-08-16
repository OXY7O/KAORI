from __future__ import annotations

from typing import Any

PER_PAGE_OPTIONS = [5, 10, 25, 50]

DOMAIN_OPTIONS = [
    {'value': '', 'label': 'All Asset Domains'},
    {'value': 'kubernetes', 'label': 'Kubernetes'},
    {'value': 'object_storage', 'label': 'Object Storage'},
    {'value': 'server', 'label': 'Server'},
    {'value': 'hci', 'label': 'HCI'},
]
PROVIDER_OPTIONS = [
    {'value': '', 'label': 'All Provider Coverage'},
    {'value': 'minio', 'label': 'MinIO'},
]
CATEGORY_OPTIONS = [
    {'value': '', 'label': 'All Categories'},
    {'value': 'capacity', 'label': 'Capacity'},
    {'value': 'governance', 'label': 'Governance'},
    {'value': 'reliability', 'label': 'Reliability'},
    {'value': 'operations', 'label': 'Operations'},
    {'value': 'optimization', 'label': 'Optimization'},
    {'value': 'performance', 'label': 'Performance'},
]
SEVERITY_OPTIONS = [
    {'value': '', 'label': 'All Severities'},
    {'value': 'critical', 'label': 'Critical'},
    {'value': 'warning', 'label': 'Warning'},
    {'value': 'info', 'label': 'Info'},
]
STATUS_OPTIONS = [
    {'value': '', 'label': 'All Statuses'},
    {'value': 'available', 'label': 'Available'},
    {'value': 'reserved', 'label': 'Reserved Plan'},
    {'value': 'imported_signal', 'label': 'Imported Signal'},
]
SOURCE_KIND_OPTIONS = [
    {'value': '', 'label': 'All Resource Types'},
    {'value': 'cluster', 'label': 'Cluster'},
    {'value': 'node', 'label': 'Node'},
    {'value': 'namespace', 'label': 'Namespace'},
    {'value': 'workload', 'label': 'Workload'},
    {'value': 'pod', 'label': 'Pod'},
    {'value': 'persistent_volume', 'label': 'Persistent Volume'},
    {'value': 'tls_secret', 'label': 'TLS Secret'},
    {'value': 'object_storage_system', 'label': 'Object Storage System'},
    {'value': 'object_storage_bucket', 'label': 'Object Storage Bucket'},
    {'value': 'vm', 'label': 'VM'},
    {'value': 'datastore', 'label': 'Datastore'},
    {'value': 'hci_cluster', 'label': 'HCI Cluster'},
]
LOGIC_TYPE_OPTIONS = [
    {'value': '', 'label': 'All Logic Types'},
    {'value': 'recommendation', 'label': 'Recommendation'},
    {'value': 'governance_check', 'label': 'Governance Check'},
    {'value': 'forecast_insight', 'label': 'Forecast Insight'},
    {'value': 'metric_signal', 'label': 'Metric Signal'},
    {'value': 'alert_enrichment', 'label': 'Alert Enrichment'},
    {'value': 'operational_hygiene', 'label': 'Operational Hygiene'},
]
SIGNAL_SOURCE_OPTIONS = [
    {'value': '', 'label': 'All Signal Sources'},
    {'value': 'kubernetes_api', 'label': 'Kubernetes API'},
    {'value': 'kaori_kubernetes_analysis', 'label': 'KAORI Kubernetes Analysis'},
    {'value': 'object_storage_inventory', 'label': 'Object Storage Inventory'},
    {'value': 'kaori_object_storage_analysis', 'label': 'KAORI Object Storage Analysis'},
    {'value': 'alertmanager', 'label': 'Alertmanager'},
    {'value': 'prometheus_metrics', 'label': 'Prometheus Metrics'},
    {'value': 'server_inventory', 'label': 'Server Node Exporter'},
    {'value': 'hci_provider_api', 'label': 'HCI API'},
]


def clean(value: str | None) -> str:
    return (value or '').strip()


def to_int(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def format_label(value: str) -> str:
    return value.replace('_', ' ').title()


def domain_label(value: str) -> str:
    return {
        'kubernetes': 'Kubernetes',
        'object_storage': 'Object Storage',
        'server': 'Server',
        'hci': 'HCI',
    }.get(value, format_label(value))


def status_label(value: str) -> str:
    return {
        'available': 'Available',
        'reserved': 'Reserved Plan',
        'imported_signal': 'Imported Signal',
    }.get(value, format_label(value))


def signal_label(value: str) -> str:
    return {
        'kubernetes_api': 'Kubernetes API',
        'kaori_kubernetes_analysis': 'KAORI Kubernetes Analysis',
        'object_storage_inventory': 'Object Storage Inventory',
        'kaori_object_storage_analysis': 'KAORI Object Storage Analysis',
        'alertmanager': 'Alertmanager',
        'prometheus_metrics': 'Prometheus Metrics',
        'server_inventory': 'Server Node Exporter',
        'hci_provider_api': 'HCI API',
    }.get(value, format_label(value))


def logic_label(value: str) -> str:
    return {
        'recommendation': 'Recommendation',
        'governance_check': 'Governance Check',
        'forecast_insight': 'Forecast Insight',
        'metric_signal': 'Metric Signal',
        'alert_enrichment': 'Alert Enrichment',
        'operational_hygiene': 'Operational Hygiene',
    }.get(value, format_label(value))


def provider_keys(rule: dict[str, Any]) -> list[str]:
    values = rule.get('provider_keys')
    if isinstance(values, (list, tuple, set)):
        return sorted({clean(str(value)).lower() for value in values if clean(str(value))})

    evidence = rule.get('evidence')
    if isinstance(evidence, dict):
        provider_key = clean(str(evidence.get('provider_key') or '')).lower()
        if provider_key:
            return [provider_key]
    return []


def provider_label(keys: list[str]) -> str:
    labels = {'minio': 'MinIO'}
    if not keys:
        return 'Domain-owned'
    return ', '.join(labels.get(key, format_label(key)) for key in keys)


def normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    domain = str(rule['domain'])
    status = str(rule['status'])
    severity = str(rule['severity'])
    category = str(rule['category'])
    source_kind = str(rule['source_kind'])
    logic_type = str(rule.get('logic_type', 'recommendation'))
    signal_source = str(rule.get('signal_source', 'kaori_kubernetes_analysis'))
    keys = provider_keys(rule)
    return {
        **rule,
        'provider_keys': keys,
        'provider_label': provider_label(keys),
        'domain_label': domain_label(domain),
        'status_label': status_label(status),
        'severity_label': format_label(severity),
        'category_label': format_label(category),
        'source_kind_label': format_label(source_kind),
        'logic_type_label': logic_label(logic_type),
        'signal_source_label': signal_label(signal_source),
        'tone': {
            'critical': 'critical',
            'warning': 'warning',
            'info': 'info',
        }.get(severity, 'unknown'),
        'status_tone': {
            'available': 'normal',
            'reserved': 'unknown',
            'imported_signal': 'maintenance',
        }.get(status, 'unknown'),
    }


def matches(rule: dict[str, Any], filters: dict[str, str]) -> bool:
    for key in ['domain', 'category', 'severity', 'status', 'source_kind', 'logic_type', 'signal_source']:
        selected = clean(filters.get(key))
        current_value = clean(str(rule.get(key, '')))
        if selected and current_value != selected:
            return False

    selected_provider = clean(filters.get('provider')).lower()
    if selected_provider and selected_provider not in provider_keys(rule):
        return False

    query = clean(filters.get('q')).lower()
    if not query:
        return True

    evidence = rule.get('evidence')
    evidence_text = ' '.join(f'{key} {value}' for key, value in evidence.items()) if isinstance(evidence, dict) else ''
    fix_steps = rule.get('fix_steps')
    fix_steps_text = ' '.join(str(step) for step in fix_steps) if isinstance(fix_steps, list) else ''
    searchable_fields = [
        'rule_key',
        'title',
        'summary',
        'condition_summary',
        'recommended_action',
        'impact',
        'evidence_boundary',
        'affected_summary',
        'domain_label',
        'category_label',
        'severity_label',
        'status_label',
        'source_kind_label',
        'logic_type_label',
        'signal_source_label',
        'provider_label',
    ]
    haystack = ' '.join([str(rule.get(field, '')) for field in searchable_fields] + [evidence_text, fix_steps_text])
    return query in haystack.lower()
