from __future__ import annotations

from datetime import datetime
from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.analytics.alerts.service import get_alerts_context
from app.intelligence.recommendation_engine import build_alerts_actionable_recommendations
from app.models.report import Report
from app.reports.export.helpers import (
    _as_pdf_list,
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
    format_datetime,
)


def build_alerts_anomalies_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_alerts_anomalies_payload(
        report,
    )

    if payload.get('_error'):
        return build_alerts_anomalies_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'active_alerts',
            'alert_severity_summary',
            'source_health',
            'routing_grouping',
            'silence_inhibition',
            'ownership_runbook',
            'incident_readiness',
            'anomaly_context',
            'affected_resources',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Alerts & Anomalies Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Alerts & Anomalies service. '
                'Alert data may come from Alertmanager or Prometheus ALERTS depending on the selected source and fallback behavior. '
                'Anomaly candidates are derived from Prometheus restart and pod readiness signals.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    rendered_sections: set[str] = set()

    if 'executive_summary' in sections:
        story.extend(
            build_alerts_executive_summary(
                report,
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'executive_summary',
        )

    if 'active_alerts' in sections:
        story.extend(
            build_active_alerts_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'active_alerts',
        )

    if 'alert_severity_summary' in sections:
        story.extend(
            build_alert_severity_summary_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'alert_severity_summary',
        )

    if 'source_health' in sections:
        story.extend(
            build_source_health_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'source_health',
        )

    if 'routing_grouping' in sections:
        story.extend(
            build_routing_grouping_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'routing_grouping',
        )

    if 'silence_inhibition' in sections:
        story.extend(
            build_silence_inhibition_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'silence_inhibition',
        )

    if 'ownership_runbook' in sections:
        story.extend(
            build_ownership_runbook_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'ownership_runbook',
        )

    if 'incident_readiness' in sections:
        story.extend(
            build_incident_readiness_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'incident_readiness',
        )

    if 'anomaly_context' in sections:
        story.extend(
            build_anomaly_context_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'anomaly_context',
        )

    if 'affected_resources' in sections:
        story.extend(
            build_affected_resources_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'affected_resources',
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_alerts_recommendations_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'operational_recommendations',
        )

    for section in sections:
        if section in rendered_sections:
            continue

        story.extend(
            build_single_section_content(
                section,
                styles,
            )
        )

    return story


def get_report_alerts_anomalies_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        context = get_alerts_context(
            cluster_id=report.cluster_id,
            source='auto',
            severity='all',
            status='all',
            namespace=report.namespace or '',
            search='',
            page=1,
            alerts_per_page=50,
            anomalies_per_page=50,
        )

        selected_cluster = context.get(
            'selected_cluster',
        )

        actionable_recommendations = build_alerts_actionable_recommendations(
            {
                'alerts': context.get(
                    'all_alerts',
                    context.get(
                        'alerts',
                        [],
                    ),
                ),
                'all_alerts': context.get(
                    'all_alerts',
                    context.get(
                        'alerts',
                        [],
                    ),
                ),
                'anomalies': context.get(
                    'all_anomalies',
                    context.get(
                        'anomalies',
                        [],
                    ),
                ),
                'all_anomalies': context.get(
                    'all_anomalies',
                    context.get(
                        'anomalies',
                        [],
                    ),
                ),
                'summary': context.get(
                    'summary',
                    {},
                ),
                'source_status': context.get(
                    'source_status',
                    {},
                ),
                'selected_cluster_signal_overview': context.get(
                    'selected_cluster_signal_overview',
                    {},
                ),
            }
        )

        return {
            'cluster': {
                'id': str(
                    getattr(
                        selected_cluster,
                        'id',
                        report.cluster_id or '',
                    )
                ),
                'name': str(
                    getattr(
                        selected_cluster,
                        'name',
                        'Unknown Cluster',
                    )
                ),
                'environment': get_environment_label(getattr(selected_cluster, 'environment', None), empty=''),
                'status': str(
                    getattr(
                        selected_cluster,
                        'status',
                        '',
                    )
                    or ''
                ),
            },
            'selected_namespace': context.get(
                'selected_namespace',
                report.namespace or 'All Namespaces',
            )
            or 'All Namespaces',
            'selected_source': context.get(
                'selected_source',
                'auto',
            ),
            'selected_severity': context.get(
                'selected_severity',
                'all',
            ),
            'selected_status': context.get(
                'selected_status',
                'all',
            ),
            'source_status': context.get(
                'source_status',
                {},
            ),
            'integration_status': context.get(
                'integration_status',
                {},
            ),
            'resource_links': context.get(
                'resource_links',
                {},
            ),
            'summary': context.get(
                'summary',
                {},
            ),
            'alerts': context.get(
                'all_alerts',
                context.get(
                    'alerts',
                    [],
                ),
            ),
            'anomalies': context.get(
                'all_anomalies',
                context.get(
                    'anomalies',
                    [],
                ),
            ),
            'selected_cluster_signal_overview': context.get(
                'selected_cluster_signal_overview',
                {},
            ),
            'source_health': context.get(
                'source_health',
                {},
            ),
            'routing_summary': context.get(
                'routing_summary',
                {},
            ),
            'silence_summary': context.get(
                'silence_summary',
                {},
            ),
            'inhibition_summary': context.get(
                'inhibition_summary',
                {},
            ),
            'ownership_summary': context.get(
                'ownership_summary',
                {},
            ),
            'incident_readiness': context.get(
                'incident_readiness',
                {},
            ),
            'actionable_recommendations': actionable_recommendations,
            'recommendations': actionable_recommendations,
            'generated_at': context.get(
                'generated_at',
            ),
            'namespace_options': context.get(
                'namespace_options',
                [],
            ),
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_alerts_anomalies_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Alerts & Anomalies Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Alerts payload unavailable',
            (
                'KAORI could not load the Alerts & Anomalies payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_alerts_executive_summary(
    report: Report,
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    cluster = (
        payload.get(
            'cluster',
        )
        or {}
    )

    source_status = (
        payload.get(
            'source_status',
        )
        or {}
    )

    summary = (
        payload.get(
            'summary',
        )
        or {}
    )

    signal_overview = (
        payload.get(
            'selected_cluster_signal_overview',
        )
        or {}
    )

    priority = (
        signal_overview.get(
            'priority',
        )
        or {}
    )

    insight = (
        signal_overview.get(
            'insight',
        )
        or {}
    )

    generated_at = payload.get(
        'generated_at',
    )

    rows = [
        [
            'Selected Cluster',
            cluster.get(
                'name',
                'Unknown Cluster',
            ),
        ],
        [
            'Cluster ID',
            cluster.get(
                'id',
                report.cluster_id or '-',
            ),
        ],
        [
            'Namespace Scope',
            payload.get(
                'selected_namespace',
                'All Namespaces',
            ),
        ],
        [
            'Selected Source',
            payload.get(
                'selected_source',
                'auto',
            ),
        ],
        [
            'Resolved Source',
            source_status.get(
                'resolved_source',
                'none',
            ),
        ],
        [
            'Source Connected',
            source_status.get(
                'connected',
                False,
            ),
        ],
        [
            'Source Label',
            source_status.get(
                'label',
                '-',
            ),
        ],
        [
            'Fallback Used',
            source_status.get(
                'fallback_used',
                False,
            ),
        ],
        [
            'Response Time',
            f'{_pdf_value(source_status.get("response_time_ms", "-"))} ms',
        ],
        [
            'Active Alerts',
            summary.get(
                'active_alerts',
                0,
            ),
        ],
        [
            'Critical Alerts',
            summary.get(
                'critical_alerts',
                0,
            ),
        ],
        [
            'Warning Alerts',
            summary.get(
                'warning_alerts',
                0,
            ),
        ],
        [
            'Detected Anomalies',
            summary.get(
                'detected_anomalies',
                0,
            ),
        ],
        [
            'Priority',
            priority.get(
                'label',
                '-',
            ),
        ],
        [
            'Priority Description',
            priority.get(
                'description',
                '-',
            ),
        ],
        [
            'Dominant Signal',
            f'{_pdf_value(insight.get("dominant_signal", "-"))} ({_pdf_value(insight.get("dominant_signal_count", 0))})',  # noqa: E501
        ],
        [
            'Action Hint',
            insight.get(
                'action_hint',
                '-',
            ),
        ],
        [
            'Generated At',
            format_datetime(
                generated_at,
            )
            if isinstance(
                generated_at,
                datetime,
            )
            else _pdf_value(
                generated_at,
            ),
        ],
    ]

    return [
        Paragraph(
            'Executive Summary',
            styles['small_section_title'],
        ),
        build_key_value_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_active_alerts_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    alerts = _as_pdf_list(
        payload.get(
            'alerts',
            [],
        )
    )

    table_rows: list[list[Any]] = [
        [
            'Severity',
            'Status',
            'Alert',
            'Namespace',
            'Target',
            'Source',
        ],
    ]

    active_statuses = {
        'active',
        'firing',
        'pending',
    }

    active_alerts = [
        alert
        for alert in alerts
        if isinstance(
            alert,
            dict,
        )
        and str(
            alert.get(
                'status',
                '',
            )
        ).lower()
        in active_statuses
    ]

    for alert in active_alerts[:15]:
        table_rows.append(
            [
                _pdf_value(
                    alert.get(
                        'severity',
                        '-',
                    )
                ).title(),
                _pdf_value(
                    alert.get(
                        'status',
                        '-',
                    )
                ).title(),
                _pdf_value(
                    alert.get(
                        'name',
                        '-',
                    )
                ),
                _pdf_value(
                    alert.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    alert.get(
                        'target',
                        '-',
                    )
                ),
                _pdf_value(
                    alert.get(
                        'source',
                        '-',
                    )
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                '-',
                'No active alerts matched the selected scope.',
                '-',
                '-',
                '-',
            ]
        )

    return [
        Paragraph(
            'Active Alerts',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                2.0 * cm,
                2.0 * cm,
                4.2 * cm,
                2.7 * cm,
                3.2 * cm,
                2.1 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_alert_detail_section(
            active_alerts,
            styles,
        ),
    ]


def build_alert_detail_section(
    alerts: list[Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    table_rows: list[list[Any]] = [
        [
            'Alert',
            'Summary / Description',
            'Starts At',
            'Ends At',
        ],
    ]

    for alert in alerts[:8]:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        description = (
            alert.get(
                'description',
            )
            or alert.get(
                'summary',
            )
            or '-'
        )

        table_rows.append(
            [
                _pdf_value(
                    alert.get(
                        'name',
                        '-',
                    )
                ),
                _pdf_value(
                    description,
                ),
                _pdf_value(
                    alert.get(
                        'starts_at_display',
                        '-',
                    )
                ),
                _pdf_value(
                    alert.get(
                        'ends_at_display',
                        '-',
                    )
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                'No alert detail available.',
                '-',
                '-',
            ]
        )

    return [
        Paragraph(
            'Alert Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                3.6 * cm,
                7.2 * cm,
                2.7 * cm,
                2.7 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_alert_severity_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    alerts = _as_pdf_list(
        payload.get(
            'alerts',
            [],
        )
    )

    anomalies = _as_pdf_list(
        payload.get(
            'anomalies',
            [],
        )
    )

    severity_summary = build_alert_severity_summary(
        alerts=alerts,
        anomalies=anomalies,
    )

    table_rows: list[list[Any]] = [
        [
            'Signal',
            'Critical',
            'Warning',
            'Info',
            'None',
            'Total',
        ],
        [
            'Alerts',
            severity_summary['alerts']['critical'],
            severity_summary['alerts']['warning'],
            severity_summary['alerts']['info'],
            severity_summary['alerts']['none'],
            severity_summary['alerts']['total'],
        ],
        [
            'Anomalies',
            severity_summary['anomalies']['critical'],
            severity_summary['anomalies']['warning'],
            severity_summary['anomalies']['info'],
            severity_summary['anomalies']['none'],
            severity_summary['anomalies']['total'],
        ],
    ]

    return [
        Paragraph(
            'Alert Severity Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                4.0 * cm,
                2.4 * cm,
                2.4 * cm,
                2.4 * cm,
                2.4 * cm,
                2.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_alert_source_status_section(
            payload,
            styles,
        ),
    ]


def build_alert_severity_summary(
    *,
    alerts: list[Any],
    anomalies: list[Any],
) -> dict[str, dict[str, int]]:
    return {
        'alerts': count_signal_severity(
            alerts,
        ),
        'anomalies': count_signal_severity(
            anomalies,
        ),
    }


def count_signal_severity(
    items: list[Any],
) -> dict[str, int]:
    result = {
        'critical': 0,
        'warning': 0,
        'info': 0,
        'none': 0,
        'total': 0,
    }

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        severity = str(
            item.get(
                'severity',
                'none',
            )
            or 'none'
        ).lower()

        if severity not in result:
            severity = 'none'

        result[severity] += 1
        result['total'] += 1

    return result


def build_alert_source_status_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    source_status = (
        payload.get(
            'source_status',
        )
        or {}
    )

    integration_status = (
        payload.get(
            'integration_status',
        )
        or {}
    )

    prometheus_status = (
        integration_status.get(
            'prometheus',
        )
        or {}
    )

    alertmanager_status = (
        integration_status.get(
            'alertmanager',
        )
        or {}
    )

    rows = [
        [
            'Source',
            'Configured',
            'Connected',
            'Status',
            'Response Time',
        ],
        [
            'Resolved Source',
            source_status.get(
                'configured',
                False,
            ),
            source_status.get(
                'connected',
                False,
            ),
            source_status.get(
                'label',
                '-',
            ),
            f'{_pdf_value(source_status.get("response_time_ms", "-"))} ms',
        ],
        [
            'Prometheus',
            prometheus_status.get(
                'configured',
                False,
            ),
            prometheus_status.get(
                'connected',
                False,
            ),
            prometheus_status.get(
                'label',
                '-',
            ),
            f'{_pdf_value(prometheus_status.get("response_time_ms", "-"))} ms',
        ],
        [
            'Alertmanager',
            alertmanager_status.get(
                'configured',
                False,
            ),
            alertmanager_status.get(
                'connected',
                False,
            ),
            alertmanager_status.get(
                'label',
                '-',
            ),
            f'{_pdf_value(alertmanager_status.get("response_time_ms", "-"))} ms',
        ],
    ]

    return [
        Paragraph(
            'Alert Source Status',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.4 * cm,
                2.5 * cm,
                2.5 * cm,
                5.2 * cm,
                2.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_source_health_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    source_health = payload.get('source_health') or {}
    source_status = payload.get('source_status') or {}

    rows = [
        ['Metric', 'Value'],
        ['Health Label', source_health.get('label', '-')],
        ['Health Level', source_health.get('level', '-')],
        ['Health Score', f'{_pdf_value(source_health.get("score", 0))}/100'],
        ['Selected Source', source_health.get('selected_source', source_status.get('selected_source', '-'))],
        ['Resolved Source', source_health.get('resolved_source', source_status.get('resolved_source', '-'))],
        ['Fallback Used', source_health.get('fallback_used', source_status.get('fallback_used', False))],
        ['Description', source_health.get('description', '-')],
    ]

    checks = _as_pdf_list(source_health.get('checks', []))
    check_rows: list[list[Any]] = [
        ['Check', 'Status', 'Description'],
    ]

    for check in checks[:8]:
        if not isinstance(check, dict):
            continue

        check_rows.append(
            [
                _pdf_value(check.get('label', '-')),
                _pdf_value(check.get('status', '-')).title(),
                _pdf_value(check.get('description', '-')),
            ]
        )

    if len(check_rows) == 1:
        check_rows.append(['-', '-', 'No source health checks were available.'])

    return [
        Paragraph('Alert Source Health', styles['small_section_title']),
        build_key_value_table(rows, styles),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            check_rows,
            styles,
            col_widths=[4.0 * cm, 2.6 * cm, 9.6 * cm],
        ),
        Spacer(1, 0.3 * cm),
    ]


def build_routing_grouping_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    routing_summary = payload.get('routing_summary') or {}

    rows = [
        ['Metric', 'Value'],
        ['Routing Status', routing_summary.get('label', '-')],
        ['Routing Level', routing_summary.get('level', '-')],
        ['Resolved Source', routing_summary.get('source', '-')],
        ['Routing Enabled', routing_summary.get('enabled', False)],
        ['Receivers', routing_summary.get('receiver_count', 0)],
        ['Groups', routing_summary.get('group_count', 0)],
        ['Fingerprints', routing_summary.get('fingerprint_count', 0)],
        ['Namespaces', routing_summary.get('namespace_count', 0)],
        ['Description', routing_summary.get('description', '-')],
    ]

    group_rows: list[list[Any]] = [
        ['Grouping Type', 'Label', 'Count', 'Percent'],
    ]

    for group_type, key in [
        ('Receiver', 'receiver_groups'),
        ('Namespace', 'namespace_groups'),
        ('Severity', 'severity_groups'),
    ]:
        for item in _as_pdf_list(routing_summary.get(key, []))[:5]:
            if not isinstance(item, dict):
                continue

            group_rows.append(
                [
                    group_type,
                    _pdf_value(item.get('label', '-')),
                    _pdf_value(item.get('count', 0)),
                    f'{_pdf_value(item.get("percent", 0))}%',
                ]
            )

    if len(group_rows) == 1:
        group_rows.append(['-', 'No routing or grouping rows available.', '-', '-'])

    return [
        Paragraph('Alert Routing & Grouping', styles['small_section_title']),
        build_key_value_table(rows, styles),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            group_rows,
            styles,
            col_widths=[3.0 * cm, 7.0 * cm, 2.4 * cm, 3.8 * cm],
        ),
        Spacer(1, 0.3 * cm),
    ]


def build_silence_inhibition_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    silence_summary = payload.get('silence_summary') or {}
    inhibition_summary = payload.get('inhibition_summary') or {}

    rows = [
        ['Metric', 'Value'],
        ['Silence Status', silence_summary.get('label', '-')],
        ['Silence Level', silence_summary.get('level', '-')],
        ['Active Silences', silence_summary.get('active_silences', 0)],
        ['Pending Silences', silence_summary.get('pending_silences', 0)],
        ['Expired Silences', silence_summary.get('expired_silences', 0)],
        ['Silence Matched Alerts', silence_summary.get('matched_alerts', 0)],
        ['Inhibition Status', inhibition_summary.get('label', '-')],
        ['Inhibition Level', inhibition_summary.get('level', '-')],
        ['Inhibited Alerts', inhibition_summary.get('matched_alerts', 0)],
        ['Inhibition Rules Detected', inhibition_summary.get('rules_detected', 0)],
    ]

    item_rows: list[list[Any]] = [
        ['Created By', 'Window', 'Matched Alerts', 'Comment'],
    ]

    for item in _as_pdf_list(silence_summary.get('items', []))[:5]:
        if not isinstance(item, dict):
            continue

        item_rows.append(
            [
                _pdf_value(item.get('created_by', '-')),
                f'{_pdf_value(item.get("starts_at", "-"))} -> {_pdf_value(item.get("ends_at", "-"))}',
                _pdf_value(item.get('matched_alerts', 0)),
                _pdf_value(item.get('comment', '-')),
            ]
        )

    if len(item_rows) == 1:
        item_rows.append(['-', '-', 0, 'No active silence detail available.'])

    return [
        Paragraph('Silence & Inhibition Visibility', styles['small_section_title']),
        build_key_value_table(rows, styles),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            item_rows,
            styles,
            col_widths=[3.0 * cm, 5.0 * cm, 2.6 * cm, 5.6 * cm],
        ),
        Spacer(1, 0.3 * cm),
    ]


def build_ownership_runbook_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    ownership_summary = payload.get('ownership_summary') or {}

    rows = [
        ['Metric', 'Value'],
        ['Readiness Label', ownership_summary.get('label', '-')],
        ['Readiness Level', ownership_summary.get('level', '-')],
        ['Readiness Score', f'{_pdf_value(ownership_summary.get("score", 0))}/100'],
        ['Alert Coverage', ownership_summary.get('alert_count', 0)],
        ['Owners', ownership_summary.get('owner_count', 0)],
        ['Runbooks', ownership_summary.get('runbook_count', 0)],
        ['Contacts', ownership_summary.get('contact_count', 0)],
        ['Missing Owners', ownership_summary.get('missing_owner_count', 0)],
        ['Missing Runbooks', ownership_summary.get('missing_runbook_count', 0)],
        ['Missing Contacts', ownership_summary.get('missing_contact_count', 0)],
    ]

    owner_rows: list[list[Any]] = [
        ['Owner', 'Alerts', 'Percent'],
    ]

    for item in _as_pdf_list(ownership_summary.get('owner_groups', []))[:8]:
        if not isinstance(item, dict):
            continue

        owner_rows.append(
            [
                _pdf_value(item.get('label', '-')),
                _pdf_value(item.get('count', 0)),
                f'{_pdf_value(item.get("percent", 0))}%',
            ]
        )

    if len(owner_rows) == 1:
        owner_rows.append(['-', 0, 'No owner metadata detected.'])

    missing_rows: list[list[Any]] = [
        ['Alert', 'Namespace', 'Severity', 'Missing'],
    ]

    for item in _as_pdf_list(ownership_summary.get('missing_metadata_items', []))[:8]:
        if not isinstance(item, dict):
            continue

        missing = item.get('missing', [])
        if isinstance(missing, list):
            missing_text = ', '.join(str(part) for part in missing)
        else:
            missing_text = _pdf_value(missing)

        missing_rows.append(
            [
                _pdf_value(item.get('name', '-')),
                _pdf_value(item.get('namespace', '-')),
                _pdf_value(item.get('severity', '-')).title(),
                missing_text,
            ]
        )

    if len(missing_rows) == 1:
        missing_rows.append(['-', '-', '-', 'No missing ownership metadata detected.'])

    return [
        Paragraph('Ownership & Runbook Readiness', styles['small_section_title']),
        build_key_value_table(rows, styles),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            owner_rows,
            styles,
            col_widths=[9.0 * cm, 3.0 * cm, 4.2 * cm],
        ),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            missing_rows,
            styles,
            col_widths=[4.8 * cm, 3.2 * cm, 2.4 * cm, 5.8 * cm],
        ),
        Spacer(1, 0.3 * cm),
    ]


def build_incident_readiness_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    incident_readiness = payload.get('incident_readiness') or {}

    rows = [
        ['Metric', 'Value'],
        ['Readiness Label', incident_readiness.get('label', '-')],
        ['Readiness Level', incident_readiness.get('level', '-')],
        ['Readiness Score', f'{_pdf_value(incident_readiness.get("score", 0))}/100'],
        ['Critical Signals', incident_readiness.get('critical_signals', 0)],
        ['Warning Signals', incident_readiness.get('warning_signals', 0)],
        ['Anomaly Signals', incident_readiness.get('anomaly_signals', 0)],
        ['Source Score', f'{_pdf_value(incident_readiness.get("source_score", 0))}/100'],
        ['Ownership Score', f'{_pdf_value(incident_readiness.get("ownership_score", 0))}/100'],
        ['Routing Ready', incident_readiness.get('routing_ready', False)],
        ['Silence Risk', incident_readiness.get('silence_risk', 0)],
        ['Inhibition Risk', incident_readiness.get('inhibition_risk', 0)],
        ['Recommended Action', incident_readiness.get('recommended_action', '-')],
    ]

    check_rows: list[list[Any]] = [
        ['Check', 'Status', 'Description'],
    ]

    for check in _as_pdf_list(incident_readiness.get('checks', []))[:10]:
        if not isinstance(check, dict):
            continue

        check_rows.append(
            [
                _pdf_value(check.get('label', '-')),
                _pdf_value(check.get('status', '-')).title(),
                _pdf_value(check.get('description', '-')),
            ]
        )

    if len(check_rows) == 1:
        check_rows.append(['-', '-', 'No incident readiness checks were available.'])

    return [
        Paragraph('Incident Readiness', styles['small_section_title']),
        build_key_value_table(rows, styles),
        Spacer(1, 0.2 * cm),
        build_pdf_table(
            check_rows,
            styles,
            col_widths=[4.0 * cm, 2.6 * cm, 9.6 * cm],
        ),
        Spacer(1, 0.3 * cm),
    ]


def build_anomaly_context_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    anomalies = _as_pdf_list(
        payload.get(
            'anomalies',
            [],
        )
    )

    table_rows: list[list[Any]] = [
        [
            'Severity',
            'Anomaly',
            'Namespace',
            'Target',
            'Signal',
            'Source',
        ],
    ]

    for anomaly in anomalies[:15]:
        if not isinstance(
            anomaly,
            dict,
        ):
            continue

        table_rows.append(
            [
                _pdf_value(
                    anomaly.get(
                        'severity',
                        '-',
                    )
                ).title(),
                _pdf_value(
                    anomaly.get(
                        'name',
                        '-',
                    )
                ),
                _pdf_value(
                    anomaly.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    anomaly.get(
                        'target',
                        '-',
                    )
                ),
                _pdf_value(
                    anomaly.get(
                        'signal',
                        '-',
                    )
                ),
                _pdf_value(
                    anomaly.get(
                        'source',
                        '-',
                    )
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                'No anomaly candidates matched the selected scope.',
                '-',
                '-',
                '-',
                '-',
            ]
        )

    return [
        Paragraph(
            'Anomaly Context',
            styles['small_section_title'],
        ),
        Paragraph(
            'Anomaly candidates are currently derived from pod restart spike and pod readiness metrics.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                2.0 * cm,
                3.4 * cm,
                2.7 * cm,
                3.2 * cm,
                2.8 * cm,
                2.1 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_anomaly_detail_section(
            anomalies,
            styles,
        ),
    ]


def build_anomaly_detail_section(
    anomalies: list[Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    table_rows: list[list[Any]] = [
        [
            'Anomaly',
            'Description',
        ],
    ]

    for anomaly in anomalies[:8]:
        if not isinstance(
            anomaly,
            dict,
        ):
            continue

        table_rows.append(
            [
                _pdf_value(
                    anomaly.get(
                        'name',
                        '-',
                    )
                ),
                _pdf_value(
                    anomaly.get(
                        'description',
                        anomaly.get(
                            'summary',
                            '-',
                        ),
                    )
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                'No anomaly detail available.',
            ]
        )

    return [
        Paragraph(
            'Anomaly Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                4.0 * cm,
                12.2 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_affected_resources_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    alerts = _as_pdf_list(
        payload.get(
            'alerts',
            [],
        )
    )

    anomalies = _as_pdf_list(
        payload.get(
            'anomalies',
            [],
        )
    )

    affected_rows = build_affected_resource_rows(
        alerts=alerts,
        anomalies=anomalies,
    )

    table_rows: list[list[Any]] = [
        [
            'Namespace',
            'Target',
            'Alerts',
            'Anomalies',
            'Highest Severity',
        ],
    ]

    for row in affected_rows[:15]:
        table_rows.append(
            [
                row['namespace'],
                row['target'],
                row['alerts'],
                row['anomalies'],
                row['highest_severity'],
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                '-',
                0,
                0,
                'No affected resources found.',
            ]
        )

    return [
        Paragraph(
            'Affected Resources',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                3.2 * cm,
                4.4 * cm,
                2.4 * cm,
                2.4 * cm,
                3.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_affected_resource_rows(
    *,
    alerts: list[Any],
    anomalies: list[Any],
) -> list[dict[str, Any]]:
    resource_map: dict[str, dict[str, Any]] = {}

    for alert in alerts:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        add_affected_resource_signal(
            resource_map=resource_map,
            item=alert,
            signal_type='alerts',
        )

    for anomaly in anomalies:
        if not isinstance(
            anomaly,
            dict,
        ):
            continue

        add_affected_resource_signal(
            resource_map=resource_map,
            item=anomaly,
            signal_type='anomalies',
        )

    return sorted(
        resource_map.values(),
        key=lambda row: (
            severity_sort_weight(
                row.get(
                    'highest_severity',
                    'none',
                )
            ),
            int(
                row.get(
                    'alerts',
                    0,
                )
            )
            + int(
                row.get(
                    'anomalies',
                    0,
                )
            ),
            row.get(
                'namespace',
                '',
            ),
        ),
        reverse=True,
    )


def add_affected_resource_signal(
    *,
    resource_map: dict[str, dict[str, Any]],
    item: dict[str, Any],
    signal_type: str,
) -> None:
    namespace = str(
        item.get(
            'namespace',
            '-',
        )
        or '-'
    )

    target = str(
        item.get(
            'target',
            '-',
        )
        or '-'
    )

    key = f'{namespace}/{target}'

    if key not in resource_map:
        resource_map[key] = {
            'namespace': namespace,
            'target': target,
            'alerts': 0,
            'anomalies': 0,
            'highest_severity': 'none',
        }

    resource_map[key][signal_type] += 1

    current_severity = str(
        resource_map[key].get(
            'highest_severity',
            'none',
        )
    ).lower()

    item_severity = str(
        item.get(
            'severity',
            'none',
        )
    ).lower()

    if severity_sort_weight(
        item_severity,
    ) > severity_sort_weight(
        current_severity,
    ):
        resource_map[key]['highest_severity'] = item_severity.title()


def severity_sort_weight(
    severity: str,
) -> int:
    weights = {
        'critical': 4,
        'warning': 3,
        'info': 2,
        'none': 1,
        '-': 0,
    }

    return weights.get(
        str(
            severity,
        ).lower(),
        0,
    )


def build_alerts_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = payload.get(
        'actionable_recommendations',
        payload.get(
            'recommendations',
            [],
        ),
    )

    resource_links = (
        payload.get(
            'resource_links',
        )
        or {}
    )

    rows: list[list[Any]] = [
        [
            'No',
            'Recommendation',
            'Priority',
            'Source',
        ],
    ]

    if isinstance(
        recommendations,
        list,
    ):
        for index, item in enumerate(
            recommendations,
            start=1,
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            rows.append(
                [
                    str(
                        index,
                    ),
                    _pdf_value(
                        item.get(
                            'title',
                            '-',
                        )
                    ),
                    _pdf_value(
                        item.get(
                            'priority',
                            item.get(
                                'severity',
                                '-',
                            ),
                        )
                    ),
                    _pdf_value(
                        item.get(
                            'source_label',
                            item.get(
                                'source',
                                '-',
                            ),
                        )
                    ),
                ]
            )
            rows.append(
                [
                    '',
                    _pdf_value(
                        item.get(
                            'description',
                            '-',
                        )
                    ),
                    _pdf_value(
                        'Actionable'
                        if str(
                            item.get(
                                'is_actionable',
                                'No',
                            )
                        )
                        == 'Yes'
                        else 'Context'
                    ),
                    '',
                ]
            )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '1',
                'Review alert posture',
                'Info',
                'Alerts & Anomalies',
            ]
        )
        rows.append(
            [
                '',
                'No actionable alert recommendation was generated. Continue monitoring alert and anomaly signals.',
                'Context',
                '',
            ]
        )

    story: list[Any] = [
        Paragraph(
            'Actionable Recommendations from Alerts & Anomalies',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                1.2 * cm,
                8.2 * cm,
                2.4 * cm,
                4.4 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]

    story.extend(
        build_alert_resource_links_section(
            resource_links,
            styles,
        )
    )

    return story


def build_alert_resource_links_section(
    resource_links: Any,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    if not isinstance(
        resource_links,
        dict,
    ):
        resource_links = {}

    rows: list[list[Any]] = [
        [
            'Resource',
            'Configured',
            'Description',
        ],
    ]

    for key in [
        'alertmanager',
        'runbook',
        'contact_point',
    ]:
        item = resource_links.get(
            key,
            {},
        )

        if not isinstance(
            item,
            dict,
        ):
            item = {}

        rows.append(
            [
                _pdf_value(
                    item.get(
                        'label',
                        key.replace(
                            '_',
                            ' ',
                        ).title(),
                    )
                ),
                _pdf_value(
                    item.get(
                        'configured',
                        False,
                    )
                ),
                _pdf_value(
                    item.get(
                        'description',
                        '-',
                    )
                ),
            ]
        )

    return [
        Paragraph(
            'Response Resources',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                4.0 * cm,
                2.4 * cm,
                9.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]
