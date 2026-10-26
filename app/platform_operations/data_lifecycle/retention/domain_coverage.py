"""Read-only coverage descriptors for governed retention domains."""

from __future__ import annotations

from app.platform_operations.data_lifecycle.retention import generated_report_presentation as generated_report_ui


def _domain_coverage(name: str) -> tuple[dict[str, str], ...]:
    return {
        'operational_activity': (
            {
                'icon': 'scroll-text',
                'label': 'Activity Audit Table',
                'description': 'All persisted administrative and operational activity records.',
            },
            {
                'icon': 'bell',
                'label': 'Notification Center',
                'description': 'Persistent user-targeted notifications share the same source table.',
            },
            {
                'icon': 'shield-check',
                'label': 'Authentication Audit',
                'description': 'Authentication events remain lifecycle-managed with the audit stream.',
            },
        ),
        'job_execution': (
            {
                'icon': 'workflow',
                'label': 'Jobs & Executions',
                'description': 'Terminal execution records, subscribers, results, and worker evidence.',
            },
        ),
        'runtime_observation': (
            {
                'icon': 'boxes',
                'label': 'Kubernetes',
                'description': 'Recent Kubernetes runtime observations.',
            },
            {
                'icon': 'gauge',
                'label': 'Metrics Source',
                'description': 'Recent Metrics Source observations.',
            },
            {
                'icon': 'bell-ring',
                'label': 'Alertmanager',
                'description': 'Recent Alertmanager runtime observations.',
            },
            {
                'icon': 'database',
                'label': 'Object Storage · MinIO',
                'description': 'Recent MinIO storage observations.',
            },
        ),
        'generated_report': generated_report_ui.GENERATED_REPORT_COVERAGE,
        'alert_incident': (
            {
                'icon': 'siren',
                'label': 'Closed Alert Cases',
                'description': 'Verified closed cases retain searchable identity while heavy evidence moves to governed archive storage.',
            },
            {
                'icon': 'list-tree',
                'label': 'Incident Timeline',
                'description': 'Case lifecycle evidence from initial detection through final closure.',
            },
            {
                'icon': 'send',
                'label': 'Notification Delivery',
                'description': 'Firing and resolved channel-delivery evidence is preserved with the incident archive.',
            },
            {
                'icon': 'file-text',
                'label': 'Postmortem Evidence',
                'description': 'Required or completed postmortem context and action-item evidence remain part of the case record.',
            },
        ),
        'audit_event': (
            {
                'icon': 'file-clock',
                'label': 'Administrative Source Evidence',
                'description': (
                    'Committed hot AuditEvent records, including allowlisted Automatic Job '
                    'and Tenant Inventory Sync sources.'
                ),
            },
            {
                'icon': 'shield-check',
                'label': 'Source Permission Boundary',
                'description': (
                    'Other AuditEvent producers remain authoritative; archive export is held for security review.'
                ),
            },
        ),
        'notification_delivery': (
            {
                'icon': 'send',
                'label': 'Notification Channels / Delivery Activity',
                'description': 'Hot committed delivery journal, retries, deduplication and provider outcomes.',
            },
            {
                'icon': 'archive',
                'label': 'Verified Archive Bundles',
                'description': 'Redacted terminal evidence using shared immutable archive storage.',
            },
        ),
        'tenant_audit_evidence': (
            {
                'icon': 'shield-check',
                'label': 'Tenant Audit Correlation',
                'description': 'Committed normalized Kubernetes audit observations linked to managed Tenants.',
            },
            {
                'icon': 'fingerprint',
                'label': 'Identity & Outcome Evidence',
                'description': 'Principal classification, resource/verb, outcome and correlation references.',
            },
        ),
        'analytics_snapshot': (
            {
                'icon': 'chart-spline',
                'label': 'Analytics Materialization',
                'description': 'Capacity, utilization, storage, workload, top-consumer, and alert datasets.',
            },
            {
                'icon': 'line-chart',
                'label': 'Forecast History',
                'description': 'Reusable forecast snapshots stored in the shared analytics snapshot table.',
            },
            {
                'icon': 'layout-dashboard',
                'label': 'Dashboard Evidence',
                'description': 'Shared materialized alert evidence reused by Kubernetes dashboards.',
            },
        ),
    }.get(name, ())
