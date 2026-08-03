from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_PAGE_COUNT = 9
_MAX_REGISTER_ROWS = 10


def build_tls_certificate_health_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    records = [_record(item) for item in _rows(payload.get('records'))]
    summary = _mapping(payload.get('summary'))
    policy = _mapping(payload.get('validity_policy'))
    source_rows = _source_rows(payload.get('source_evidence'))
    schema = _mapping(payload.get('schema_readiness'))
    sensitive_policy = _mapping(payload.get('sensitive_data_policy'))
    cluster = _mapping(payload.get('cluster'))

    validity_rows = [_validity_row(item, index) for index, item in enumerate(records[:_MAX_REGISTER_ROWS], 1)]
    expiry_records = [
        item for item in records if item['status'] in {'expired', 'invalid', 'critical', 'warning'}
    ]
    expiry_rows = [_expiry_row(item, index) for index, item in enumerate(expiry_records[:_MAX_REGISTER_ROWS], 1)]
    usage_rows = [_usage_row(item, index) for index, item in enumerate(records[:_MAX_REGISTER_ROWS], 1)]
    validation_rows = [_validation_row(item, index) for index, item in enumerate(records[:_MAX_REGISTER_ROWS], 1)]
    recommendations = _recommendations(records, summary, schema)
    risks = _risk_rows(records, summary, schema)

    total = _int(summary.get('total'))
    in_use = _int(summary.get('in_use'))
    expired_in_use = _int(summary.get('expired_in_use'))
    critical_in_use = _int(summary.get('critical_in_use'))
    warning_in_use = _int(summary.get('warning_in_use'))
    invalid_in_use = _int(summary.get('invalid_in_use'))
    uncovered_in_use = _int(summary.get('uncovered_in_use'))
    action_required = _int(summary.get('action_required'))
    collection_exceptions = _int(summary.get('collection_exceptions'))
    schema_ready = bool(schema.get('ready', True))

    primary = _executive_interpretation(
        total=total,
        expired_in_use=expired_in_use,
        critical_in_use=critical_in_use,
        invalid_in_use=invalid_in_use,
        uncovered_in_use=uncovered_in_use,
        warning_in_use=warning_in_use,
        collection_exceptions=collection_exceptions,
        schema_ready=schema_ready,
    )

    return {
        'presentation_version': 'v1.0-tls-certificate-health-publication',
        'page_count': _PAGE_COUNT,
        'layout_contract': {
            'paper': 'A4 Portrait',
            'page_count': _PAGE_COUNT,
            'fixed_page_canvas': True,
            'source_policy': 'committed-db-snapshot-only',
            'usage_policy': 'committed-reference-evidence',
            'private_key_policy': 'never-collected-or-rendered',
            'missing_evidence_policy': 'explicit-not-available',
            'visual_style': 'kaori-tls-certificate-health-v1.0',
        },
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'TLS Certificate Health & Expiry',
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': sanitize_text(cluster.get('environment'), fallback='Not Available'),
            'purpose': (
                'Identify valid, renewal-window, critical, expired, invalid, unused, and '
                'unmapped TLS certificates from committed Kubernetes governance evidence.'
            ),
            'context': (
                'Usage and certificate validity are evaluated independently. PDF rendering reads '
                'persisted certificate metadata only and never reads Kubernetes Secret values.'
            ),
        },
        'executive': {
            'metrics': [
                _metric('TLS Secrets', str(total), 'Committed inventory', 'normal' if total else 'muted'),
                _metric('In Use', str(in_use), 'Committed references', 'normal' if in_use else 'muted'),
                _metric('Action Required', str(action_required), 'Expired / critical / invalid / SAN', 'critical' if action_required else 'normal'),
                _metric('Renewal Window', str(warning_in_use), 'In-use certificates', 'warning' if warning_in_use else 'normal'),
            ],
            'posture_rows': [
                _posture_row('F1', 'Expired + In Use', expired_in_use, 'Critical' if expired_in_use else 'Clear', 'critical' if expired_in_use else 'normal'),
                _posture_row('F2', 'Critical Expiry + In Use', critical_in_use, 'Critical' if critical_in_use else 'Clear', 'critical' if critical_in_use else 'normal'),
                _posture_row('F3', 'Invalid + In Use', invalid_in_use, 'Critical' if invalid_in_use else 'Clear', 'critical' if invalid_in_use else 'normal'),
                _posture_row('F4', 'Uncovered Host + In Use', uncovered_in_use, 'Review' if uncovered_in_use else 'Clear', 'warning' if uncovered_in_use else 'normal'),
                _posture_row('F5', 'Renewal Window + In Use', warning_in_use, 'Review' if warning_in_use else 'Clear', 'warning' if warning_in_use else 'normal'),
            ],
            'interpretation_title': primary['title'],
            'interpretation_body': primary['body'],
            'interpretation_note': primary['note'],
            'tone': primary['tone'],
            'decisions': recommendations[:4],
        },
        'validity': {
            'metrics': [
                _metric('Valid', str(_int(summary.get('healthy'))), f"> {policy.get('renewal_window_days', 30)} days", 'normal'),
                _metric('Renewal Window', str(_int(summary.get('warning'))), f"<= {policy.get('renewal_window_days', 30)} days", 'warning'),
                _metric('Critical Expiry', str(_int(summary.get('critical'))), f"<= {policy.get('critical_window_days', 7)} days", 'critical'),
                _metric('Expired / Invalid', str(_int(summary.get('expired')) + _int(summary.get('invalid'))), 'Requires review', 'critical'),
            ],
            'rows': validity_rows,
            'definitions': _validity_definitions(policy),
        },
        'expiry': {
            'metrics': [
                _metric('Expired In Use', str(expired_in_use), 'P1', 'critical' if expired_in_use else 'normal'),
                _metric('Critical In Use', str(critical_in_use), 'P1', 'critical' if critical_in_use else 'normal'),
                _metric('Renewal Window In Use', str(warning_in_use), 'P2', 'warning' if warning_in_use else 'normal'),
                _metric('Invalid In Use', str(invalid_in_use), 'P1', 'critical' if invalid_in_use else 'normal'),
            ],
            'rows': expiry_rows,
            'timing_rows': _renewal_timing_rows(policy),
        },
        'usage': {
            'metrics': [
                _metric('In Use', str(in_use), 'Referenced', 'normal'),
                _metric('Unused', str(_int(summary.get('unused'))), 'Review lifecycle', 'info'),
                _metric('Unknown Usage', str(_int(summary.get('unknown_usage'))), 'Mapping unavailable', 'warning'),
                _metric('Missing Secret', 'N/A', sanitize_text(summary.get('missing_secret_evidence'), fallback='Not Collected'), 'warning'),
            ],
            'rows': usage_rows,
            'collection_rows': source_rows,
        },
        'validation': {
            'metrics': [
                _metric('Certificate Parse', _coverage_label(records, 'parse_state', 'Passed'), 'Committed', 'normal'),
                _metric('Host Coverage', _coverage_label(records, 'coverage_state', 'fully_covered'), 'Ingress references', 'warning' if uncovered_in_use else 'normal'),
                _metric('Key Pair Match', sanitize_text(sensitive_policy.get('pair_validation_state'), fallback='Not Collected'), 'Data minimization', 'muted'),
                _metric('Chain Validation', sanitize_text(sensitive_policy.get('chain_validation_state'), fallback='Not Collected'), 'Data minimization', 'muted'),
            ],
            'rows': validation_rows,
            'requirements': _validation_requirements(),
            'private_key_policy': (
                'KAORI persists certificate metadata and validation outcomes only. Raw private keys, '
                'tls.key values, and recoverable secret material are excluded from report payloads.'
            ),
        },
        'risk': {
            'metrics': [
                _metric('P1 Risks', str(sum(1 for item in risks if item['priority'] == 'P1')), 'Immediate', 'critical'),
                _metric('P2 Risks', str(sum(1 for item in risks if item['priority'] == 'P2')), 'Open', 'warning'),
                _metric('P3 Risks', str(sum(1 for item in risks if item['priority'] == 'P3')), 'Planned', 'info'),
                _metric('Collection Exceptions', str(collection_exceptions), 'Source evidence', 'warning' if collection_exceptions else 'normal'),
            ],
            'rows': risks,
            'ownership_rows': _ownership_rows(records),
        },
        'recommendations': {
            'metrics': _recommendation_metrics(recommendations),
            'rows': recommendations,
            'governance': [
                {'field': 'Primary Action', 'requirement': recommendations[0]['title'] if recommendations else 'Continue TLS validity and usage monitoring.'},
                {'field': 'Validation Criteria', 'requirement': 'Confirm certificate validity, committed reference, hostname coverage, live endpoint, renewal owner, and approved rollback before closure.'},
                {'field': 'Assigned Owners', 'requirement': _owner_summary(recommendations)},
                {'field': 'Change Control', 'requirement': 'No certificate renewal, Secret replacement, or routing change is authorized by this report alone.'},
            ],
        },
        'methodology': {
            'metrics': [
                _metric('Data Sources', str(len(source_rows)), 'Cluster snapshots', 'normal' if source_rows else 'muted'),
                _metric('Renewal Window', f"{policy.get('renewal_window_days', 30)} Days", 'Configurable', 'info'),
                _metric('Critical Window', f"{policy.get('critical_window_days', 7)} Days", 'Configurable', 'critical'),
                _metric('Secret Material', 'Excluded', 'Protected', 'normal'),
            ],
            'sources': source_rows,
            'rules': [
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Usage Status', 'setting': 'Committed Ingress references'},
                {'ref': 'M4', 'rule': 'Renewal Window', 'setting': f"{policy.get('renewal_window_days', 30)} days"},
                {'ref': 'M5', 'rule': 'Critical Window', 'setting': f"{policy.get('critical_window_days', 7)} days"},
                {'ref': 'M6', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ],
            'included': [
                'Persisted certificate subject, issuer, serial, fingerprint, SAN, validity window, and parse status.',
                'Committed Ingress TLS references, declared hosts, usage state, and hostname coverage evidence.',
                'Collection status, data cut-off, validity policy, risk register, and renewal recommendations.',
            ],
            'excluded': [
                'Raw private keys, tls.key values, Secret data, or recoverable key material.',
                'Live endpoint state, live Kubernetes API reads, and changes after the committed data cut-off.',
                'Key-pair and trust-chain conclusions when validation outcomes are not persisted.',
                'Missing-secret references that are not represented by the current committed relationship model.',
            ],
            'limitations': [
                'This report describes persisted TLS governance evidence and does not replace live endpoint validation.',
                'An unused Secret may be intentional; confirm application ownership and deployment design before deletion.',
                'Unknown Usage means reference collection was unavailable, not that the Secret is unused.',
                'Certificate validity does not prove that every external endpoint presents the same certificate.',
            ],
            'status_language': [
                {'ref': 'S1', 'title': 'In Use', 'description': 'At least one committed Ingress references the TLS Secret.'},
                {'ref': 'S2', 'title': 'Unused', 'description': 'Reference collection succeeded and no committed Ingress references the Secret.'},
                {'ref': 'S3', 'title': 'Unknown Usage', 'description': 'Ingress relationship collection is unavailable or not reported.'},
                {'ref': 'S4', 'title': 'Not Collected', 'description': 'The current committed model intentionally does not store the evidence.'},
            ],
        },
    }


def _record(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'cluster': sanitize_text(value.get('cluster'), fallback='Not Available'),
        'namespace': sanitize_text(value.get('namespace'), fallback='Not Available'),
        'secret_name': sanitize_text(value.get('secret_name'), fallback='Not Available'),
        'secret_identity': sanitize_text(value.get('secret_identity'), fallback='Not Available'),
        'common_name': sanitize_text(value.get('common_name'), fallback='Not Available'),
        'issuer': sanitize_text(value.get('issuer'), fallback='Not Available'),
        'fingerprint_short': sanitize_text(value.get('fingerprint_short'), fallback='Not Available'),
        'dns_names_label': sanitize_text(value.get('dns_names_label'), fallback='Not Available'),
        'ingress_hosts_label': sanitize_text(value.get('ingress_hosts_label'), fallback='Not Available'),
        'references_label': sanitize_text(value.get('references_label'), fallback='Not Available'),
        'reference_count': _int(value.get('reference_count')),
        'usage_state': sanitize_text(value.get('usage_state'), fallback='unknown_usage'),
        'usage_label': sanitize_text(value.get('usage_label'), fallback='Unknown Usage'),
        'usage_tone': sanitize_text(value.get('usage_tone'), fallback='warning'),
        'not_before': value.get('not_before'),
        'not_after': value.get('not_after'),
        'days_remaining': _nullable_int(value.get('days_remaining')),
        'status': sanitize_text(value.get('status'), fallback='unknown').lower(),
        'status_label': sanitize_text(value.get('status_label'), fallback='Unknown'),
        'status_tone': sanitize_text(value.get('status_tone'), fallback='muted'),
        'parse_error': sanitize_text(value.get('parse_error'), fallback='') if value.get('parse_error') else '',
        'parse_state': sanitize_text(value.get('parse_state'), fallback='Not Available'),
        'parse_tone': sanitize_text(value.get('parse_tone'), fallback='warning'),
        'coverage_state': sanitize_text(value.get('coverage_state'), fallback='not_reported').lower(),
        'coverage_label': sanitize_text(value.get('coverage_label'), fallback='Not Reported'),
        'coverage_tone': sanitize_text(value.get('coverage_tone'), fallback='muted'),
        'declared_host_count': _int(value.get('declared_host_count')),
        'covered_host_count': _int(value.get('covered_host_count')),
        'uncovered_hosts_label': sanitize_text(value.get('uncovered_hosts_label'), fallback='None'),
        'collected_at': value.get('collected_at'),
        'key_pair_state': sanitize_text(value.get('key_pair_state'), fallback='Not Collected'),
        'chain_state': sanitize_text(value.get('chain_state'), fallback='Not Collected'),
    }


def _validity_row(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'T{index}',
        'cluster': item['cluster'],
        'namespace': item['namespace'],
        'secret': item['secret_name'],
        'common_name': item['common_name'],
        'not_after': _date(item.get('not_after')),
        'days': _days(item.get('days_remaining')),
        'usage': item['usage_label'],
        'usage_tone': item['usage_tone'],
        'status': item['status_label'],
        'tone': item['status_tone'],
    }


def _expiry_row(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    priority = 'P1' if item['status'] in {'expired', 'invalid', 'critical'} and item['usage_state'] == 'in_use' else 'P2'
    action = {
        'expired': 'Replace immediately',
        'invalid': 'Repair certificate evidence',
        'critical': 'Renew before expiry',
        'warning': 'Schedule renewal',
    }.get(item['status'], 'Review')
    return {
        'ref': f'E{index}',
        'priority': priority,
        'secret': item['secret_identity'],
        'host': item['ingress_hosts_label'] if item['ingress_hosts_label'] != 'Not Available' else item['common_name'],
        'not_after': _date(item.get('not_after')),
        'days': _days(item.get('days_remaining')),
        'usage': item['usage_label'],
        'usage_tone': item['usage_tone'],
        'action': action,
        'tone': 'critical' if priority == 'P1' else 'warning',
    }


def _usage_row(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'U{index}',
        'cluster': item['cluster'],
        'secret': item['secret_identity'],
        'reference_count': str(item['reference_count']),
        'referenced_by': item['references_label'],
        'usage': item['usage_label'],
        'tone': item['usage_tone'],
        'validity': item['status_label'],
        'validity_tone': item['status_tone'],
    }


def _validation_row(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'V{index}',
        'secret': item['secret_identity'],
        'parse': item['parse_state'],
        'parse_tone': item['parse_tone'],
        'hosts': str(item['declared_host_count']),
        'covered': str(item['covered_host_count']),
        'coverage': item['coverage_label'],
        'coverage_tone': item['coverage_tone'],
        'key_pair': item['key_pair_state'],
        'chain': item['chain_state'],
    }


def _recommendations(records: list[dict[str, Any]], summary: Mapping[str, Any], schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(priority: str, title: str, description: str, owner: str, target: str, status: str, tone: str) -> None:
        key = (title, description)
        if key in seen or len(rows) >= 8:
            return
        seen.add(key)
        rows.append({
            'ref': f'R{len(rows) + 1}',
            'priority': priority,
            'title': title,
            'description': description,
            'owner': owner,
            'target': target,
            'status': status,
            'tone': tone,
        })

    if not bool(schema.get('ready', True)):
        add('P1', 'Apply TLS Governance Schema Revision', sanitize_text(schema.get('detail'), fallback='TLS governance schema is not ready.'), 'Platform Operations', 'Immediate', 'Blocked', 'critical')

    for item in records:
        identity = item['secret_identity']
        if item['usage_state'] == 'in_use' and item['status'] == 'expired':
            add('P1', f'Replace Expired Certificate: {identity}', 'Renew or replace the certificate, update the referenced Secret, and validate every committed host.', 'Platform Operations', 'Immediate', 'Open', 'critical')
        elif item['usage_state'] == 'in_use' and item['status'] == 'critical':
            add('P1', f'Renew Critical Certificate: {identity}', f"Certificate has {_days(item.get('days_remaining'))} remaining and is actively referenced.", 'Platform Operations', '<=3 Days', 'Open', 'critical')
        elif item['usage_state'] == 'in_use' and item['status'] == 'invalid':
            add('P1', f'Repair Invalid Certificate: {identity}', item['parse_error'] or 'Certificate metadata is invalid or unavailable.', 'Platform Operations', 'Immediate', 'Open', 'critical')
        elif item['usage_state'] == 'in_use' and item['status'] == 'warning':
            add('P2', f'Schedule Renewal: {identity}', f"Certificate is inside the renewal window with {_days(item.get('days_remaining'))} remaining.", 'Platform Operations', '<=14 Days', 'Open', 'warning')

        if item['usage_state'] == 'in_use' and item['coverage_state'] in {'partial', 'uncovered'}:
            add('P1' if item['coverage_state'] == 'uncovered' else 'P2', f'Repair Host Coverage: {identity}', f"Declared hosts are not fully covered. Uncovered evidence: {item['uncovered_hosts_label']}.", 'Application Owner', 'This Week', 'Open', 'critical' if item['coverage_state'] == 'uncovered' else 'warning')
        if item['usage_state'] == 'unknown_usage':
            add('P2', f'Restore Usage Mapping: {identity}', 'Ingress relationship collection is unavailable. Confirm whether the Secret is actively referenced.', 'Platform Operations', 'This Week', 'Review', 'warning')
        if item['usage_state'] == 'unused' and item['status'] == 'healthy':
            add('P3', f'Review Unused Valid Secret: {identity}', 'Confirm ownership and deployment intent before retention or deletion.', 'Application Owner', 'This Month', 'Planned', 'info')

    if _int(summary.get('collection_exceptions')):
        add('P2', 'Restore TLS Collection Coverage', 'Resolve certificate or Ingress mapping collection exceptions before relying on usage conclusions.', 'Platform Operations', 'This Week', 'Open', 'warning')

    if not rows:
        add('P3', 'Maintain TLS Governance Evidence', 'Continue committed certificate and Ingress reference collection and review the renewal window regularly.', 'Platform Operations', 'This Month', 'Current', 'normal')
    return rows


def _risk_rows(records: list[dict[str, Any]], summary: Mapping[str, Any], schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(condition: str, priority: str, owner: str, status: str, tone: str, evidence: str) -> None:
        if len(rows) >= 8:
            return
        rows.append({
            'ref': f'TLS-{len(rows) + 1:02d}',
            'condition': condition,
            'priority': priority,
            'owner': owner,
            'status': status,
            'tone': tone,
            'evidence': evidence,
        })

    if not bool(schema.get('ready', True)):
        add('TLS governance schema is not ready', 'P1', 'Platform Operations', 'Blocked', 'critical', sanitize_text(schema.get('detail'), fallback='Schema readiness failed.'))
    if _int(summary.get('expired_in_use')):
        add('Expired certificate still in use', 'P1', 'Platform Operations', 'Open', 'critical', f"{_int(summary.get('expired_in_use'))} certificate(s)")
    if _int(summary.get('critical_in_use')):
        add('Certificate expires inside critical window', 'P1', 'Platform Operations', 'Open', 'critical', f"{_int(summary.get('critical_in_use'))} certificate(s)")
    if _int(summary.get('invalid_in_use')):
        add('Invalid certificate metadata still in use', 'P1', 'Platform Operations', 'Open', 'critical', f"{_int(summary.get('invalid_in_use'))} certificate(s)")
    if _int(summary.get('uncovered_in_use')):
        add('Referenced host is not fully covered', 'P1', 'Application Owner', 'Open', 'critical', f"{_int(summary.get('uncovered_in_use'))} certificate(s)")
    if _int(summary.get('warning_in_use')):
        add('Certificate is inside renewal window', 'P2', 'Platform Operations', 'Open', 'warning', f"{_int(summary.get('warning_in_use'))} certificate(s)")
    if _int(summary.get('unknown_usage')):
        add('TLS Secret usage is unknown', 'P2', 'Platform Operations', 'Review', 'warning', f"{_int(summary.get('unknown_usage'))} certificate(s)")
    if _int(summary.get('unused')):
        add('Valid TLS Secret is unused', 'P3', 'Application Owner', 'Review', 'info', f"{_int(summary.get('unused'))} certificate(s)")
    if _int(summary.get('collection_exceptions')):
        add('TLS collection coverage is incomplete', 'P2', 'Platform Operations', 'Open', 'warning', f"{_int(summary.get('collection_exceptions'))} exception(s)")
    if not rows:
        add('No committed TLS risk requires escalation', 'P3', 'Platform Operations', 'Current', 'normal', f'{len(records)} certificate record(s) reviewed')
    return rows


def _ownership_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    in_use = sum(1 for item in records if item['usage_state'] == 'in_use')
    return [
        {'ref': 'O1', 'evidence': 'Platform Owner', 'definition': 'Certificate collection, Secret deployment, and reference validation.', 'status': 'Required', 'action': 'Maintain'},
        {'ref': 'O2', 'evidence': 'Application Owner', 'definition': 'Hostname intent, service impact, and accepted renewal window.', 'status': 'Not Collected', 'action': 'Assign'},
        {'ref': 'O3', 'evidence': 'Renewal Owner', 'definition': 'Certificate issuance, replacement, and expiry tracking.', 'status': 'Not Collected', 'action': 'Assign'},
        {'ref': 'O4', 'evidence': 'In-Use Coverage', 'definition': f'{in_use} actively referenced certificate(s) require accountable service ownership.', 'status': 'Review' if in_use else 'Current', 'action': 'Validate'},
    ]


def _source_rows(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in _rows(value):
        rows.append({
            'source': sanitize_text(item.get('cluster'), fallback='TLS Governance Database'),
            'freshness': _source_status(item.get('secret_collection_status'), item.get('ingress_mapping_status')),
            'collected': _date_time(item.get('collected_at')),
            'secret_status': _humanize(item.get('secret_collection_status')),
            'mapping_status': _humanize(item.get('ingress_mapping_status')),
        })
    if not rows:
        rows.append({
            'source': 'TLS Governance Database',
            'freshness': 'Not Available',
            'collected': 'Not Available',
            'secret_status': 'Not Reported',
            'mapping_status': 'Not Reported',
        })
    return rows


def _executive_interpretation(**values: Any) -> dict[str, str]:
    if not values['schema_ready']:
        return {
            'title': 'TLS governance schema must be upgraded before report evidence is available.',
            'body': 'KAORI blocked database queries against an outdated TLS governance schema.',
            'note': 'Apply the required Alembic revision, run TLS certificate synchronization, and regenerate the report.',
            'tone': 'critical',
        }
    if values['expired_in_use']:
        return {
            'title': 'An expired certificate remains actively referenced.',
            'body': f"{values['expired_in_use']} expired in-use certificate(s) require immediate replacement and endpoint validation.",
            'note': 'Confirm every committed host, renewal owner, rollback path, and live endpoint before closure.',
            'tone': 'critical',
        }
    if values['critical_in_use'] or values['invalid_in_use'] or values['uncovered_in_use']:
        return {
            'title': 'Critical TLS lifecycle or hostname evidence requires ownership.',
            'body': f"Critical expiry: {values['critical_in_use']}; invalid: {values['invalid_in_use']}; uncovered host: {values['uncovered_in_use']}.",
            'note': 'Prioritize actively referenced certificates before unused-secret cleanup.',
            'tone': 'critical',
        }
    if values['warning_in_use'] or values['collection_exceptions']:
        return {
            'title': 'TLS renewal or collection evidence requires planned review.',
            'body': f"Renewal-window certificates: {values['warning_in_use']}; collection exceptions: {values['collection_exceptions']}.",
            'note': 'Schedule renewal and restore relationship evidence before the critical window.',
            'tone': 'warning',
        }
    if values['total']:
        return {
            'title': 'No committed in-use certificate requires immediate escalation.',
            'body': f"KAORI reviewed {values['total']} committed TLS certificate record(s) at the report cut-off.",
            'note': 'Continue scheduled certificate and Ingress reference collection.',
            'tone': 'normal',
        }
    return {
        'title': 'No committed TLS certificate evidence is available.',
        'body': 'The selected scope contains no certificate record in the current snapshot.',
        'note': 'Confirm cluster scope and run TLS certificate synchronization before drawing conclusions.',
        'tone': 'warning',
    }


def _validity_definitions(policy: Mapping[str, Any]) -> list[dict[str, str]]:
    renewal = _int(policy.get('renewal_window_days')) or 30
    critical = _int(policy.get('critical_window_days')) or 7
    return [
        {'ref': 'V1', 'status': 'Valid', 'definition': f'More than {renewal} days remaining.', 'semantic': 'Green'},
        {'ref': 'V2', 'status': 'Renewal Window', 'definition': f'{critical + 1}-{renewal} days remaining.', 'semantic': 'Amber'},
        {'ref': 'V3', 'status': 'Critical Expiry', 'definition': f'0-{critical} days remaining.', 'semantic': 'Red'},
        {'ref': 'V4', 'status': 'Expired', 'definition': 'notAfter is before the committed cut-off.', 'semantic': 'Red'},
        {'ref': 'V5', 'status': 'Invalid', 'definition': 'Certificate metadata could not be parsed.', 'semantic': 'Red'},
        {'ref': 'V6', 'status': 'Unknown', 'definition': 'Validity evidence is not available.', 'semantic': 'Slate'},
    ]


def _renewal_timing_rows(policy: Mapping[str, Any]) -> list[dict[str, str]]:
    renewal = _int(policy.get('renewal_window_days')) or 30
    critical = _int(policy.get('critical_window_days')) or 7
    return [
        {'priority': 'P1', 'window': 'Expired / Invalid', 'target': 'Immediate'},
        {'priority': 'P1', 'window': f'0-{critical} days', 'target': '<=3 Days'},
        {'priority': 'P2', 'window': f'{critical + 1}-{renewal} days', 'target': '<=14 Days'},
        {'priority': 'P3', 'window': f'> {renewal} days', 'target': 'Monitor'},
    ]


def _validation_requirements() -> list[dict[str, str]]:
    return [
        {'ref': 'K1', 'validation': 'Certificate parse', 'state': 'Collected'},
        {'ref': 'K2', 'validation': 'Validity window', 'state': 'Collected'},
        {'ref': 'K3', 'validation': 'Ingress host coverage', 'state': 'Collected when mapping succeeds'},
        {'ref': 'K4', 'validation': 'Certificate / private-key match', 'state': 'Not Collected'},
        {'ref': 'K5', 'validation': 'Trust-chain validation', 'state': 'Not Collected'},
    ]


def _recommendation_metrics(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        _metric('P1 Actions', str(sum(1 for item in rows if item.get('priority') == 'P1')), 'Immediate', 'critical'),
        _metric('P2 Actions', str(sum(1 for item in rows if item.get('priority') == 'P2')), 'Open', 'warning'),
        _metric('P3 Actions', str(sum(1 for item in rows if item.get('priority') == 'P3')), 'Planned', 'info'),
        _metric('Validation Gates', str(len(rows)), 'Required', 'info'),
    ]


def _owner_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in rows:
        owner = sanitize_text(item.get('owner'), fallback='Unassigned')
        counts[owner] = counts.get(owner, 0) + 1
    return '; '.join(f'{owner}: {count}' for owner, count in sorted(counts.items())) or 'No open action owner.'


def _posture_row(ref: str, condition: str, count: int, status: str, tone: str) -> dict[str, str]:
    return {'ref': ref, 'condition': condition, 'count': str(count), 'status': status, 'tone': tone}


def _metric(label: str, value: str, note: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'note': note, 'tone': tone}


def _coverage_label(records: Sequence[Mapping[str, Any]], field: str, expected: str) -> str:
    total = len(records)
    matched = sum(1 for item in records if item.get(field) == expected)
    return f'{matched} / {total}' if total else '0 / 0'


def _source_status(secret_status: Any, mapping_status: Any) -> str:
    secret = sanitize_text(secret_status, fallback='not_reported').lower()
    mapping = sanitize_text(mapping_status, fallback='not_reported').lower()
    if secret == 'collected' and mapping == 'collected':
        return 'Complete'
    if secret == 'collected':
        return 'Partial Mapping'
    return 'Collection Exception'


def _humanize(value: Any) -> str:
    text = sanitize_text(value, fallback='not_reported').replace('_', ' ')
    return text.title()


def _date(value: Any) -> str:
    dt = _datetime(value)
    return dt.strftime('%d %b %Y') if dt else 'Not Available'


def _date_time(value: Any) -> str:
    dt = _datetime(value)
    return dt.strftime('%d %b %Y %H:%M UTC') if dt else 'Not Available'


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        normalized = value.strip().replace('Z', '+00:00')
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _days(value: Any) -> str:
    parsed = _nullable_int(value)
    return f'{parsed} days' if parsed is not None else 'Not Available'


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _nullable_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
