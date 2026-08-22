from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from html.parser import HTMLParser
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, select_autoescape

from app.models.alert_ops import AlertCase, AlertNotificationTemplate


@dataclass(frozen=True, slots=True)
class AlertTemplateDefinition:
    provider_key: str
    event_state: str
    name: str
    subject: str | None
    body: str
    content_format: str = 'plain_text'


_PROVIDER_FORMATS: dict[str, tuple[str, ...]] = {
    'telegram': ('plain_text', 'markdown', 'html'),
    'email': ('plain_text', 'html'),
    'microsoft_teams': ('plain_text', 'markdown'),
}
_FORMAT_LABELS = {'plain_text': 'Plain Text', 'markdown': 'Markdown', 'html': 'HTML'}

_BUILT_INS: tuple[AlertTemplateDefinition, ...] = (
    AlertTemplateDefinition(
        'telegram', 'firing', 'Telegram · Firing', None,
        '🚨 FIRING · {{ severity }}\n\n{{ alert_name }}\n\nAsset\n{{ asset_name }}\n{% if namespace %}\nNamespace\n{{ namespace }}\n{% endif %}\nSummary\n{{ summary }}\n\nStarted\n{{ started_at }}\n\nCase\n{{ case_id }}{% if action_url %}\n\nOpen in KAORI\n{{ action_url }}{% endif %}',
    ),
    AlertTemplateDefinition(
        'telegram', 'resolved', 'Telegram · Resolved', None,
        '✅ RESOLVED · {{ severity }}\n\n{{ alert_name }}\n\nDuration\n{{ duration }}\n\nResolution\n{{ resolution_summary }}\n\nOperator\n{{ operator_name }}\n\nVerification\n{{ verification_evidence }}\n\nCase\n{{ case_id }}{% if action_url %}\n\nOpen Incident Record\n{{ action_url }}{% endif %}',
    ),
    AlertTemplateDefinition(
        'email', 'firing', 'Email · Firing', '[FIRING][{{ severity }}] {{ alert_name }} — {{ asset_name }}',
        'Alert: {{ alert_name }}\nSeverity: {{ severity }}\nAsset: {{ asset_name }}\nScope: {{ scope }}\nStarted: {{ started_at }}\n\nSummary\n{{ summary }}\n\nEvidence\n{{ evidence_summary }}\n\nCase: {{ case_id }}\n{% if action_url %}Open in KAORI: {{ action_url }}{% endif %}',
    ),
    AlertTemplateDefinition(
        'email', 'resolved', 'Email · Resolved', '[RESOLVED][{{ severity }}] {{ alert_name }} — {{ asset_name }}',
        'Alert: {{ alert_name }}\nSeverity: {{ severity }}\nAsset: {{ asset_name }}\nDuration: {{ duration }}\nResolved by: {{ operator_name }}\n\nResolution Summary\n{{ resolution_summary }}\n\nRemediation Steps\n{{ remediation_steps }}\n\nVerification Evidence\n{{ verification_evidence }}\n\nChange: {{ change_reference }}\nTicket: {{ ticket_reference }}\n\nCase: {{ case_id }}\n{% if action_url %}Open Incident Record: {{ action_url }}{% endif %}',
    ),
    AlertTemplateDefinition(
        'microsoft_teams', 'firing', 'Microsoft Teams · Firing', None,
        '🚨 **FIRING · {{ severity }}**\n\n**{{ alert_name }}**\n\nAsset: {{ asset_name }}\nScope: {{ scope }}\nStarted: {{ started_at }}\n\n{{ summary }}\n\nEvidence: {{ evidence_summary }}\n\nCase: {{ case_id }}{% if action_url %}\n\n{{ action_url }}{% endif %}',
        'markdown',
    ),
    AlertTemplateDefinition(
        'microsoft_teams', 'resolved', 'Microsoft Teams · Resolved', None,
        '✅ **RESOLVED · {{ severity }}**\n\n**{{ alert_name }}**\n\nDuration: {{ duration }}\nResolved by: {{ operator_name }}\n\nResolution: {{ resolution_summary }}\n\nVerification: {{ verification_evidence }}\n\nCase: {{ case_id }}{% if action_url %}\n\n{{ action_url }}{% endif %}',
        'markdown',
    ),
)

_ENV = Environment(autoescape=False, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
_HTML_ENV = Environment(
    autoescape=select_autoescape(default=True, default_for_string=True),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def built_in_templates() -> list[dict[str, Any]]:
    overrides = {
        (row.provider_key, row.event_state): row
        for row in AlertNotificationTemplate.query.filter_by(enabled=True)
        .order_by(AlertNotificationTemplate.id.desc())
        .all()
    }
    result: list[dict[str, Any]] = []
    for definition in _BUILT_INS:
        override = overrides.get((definition.provider_key, definition.event_state))
        content_format = override.content_format if override else definition.content_format
        subject_template = override.subject_template if override else definition.subject
        body_template = override.body_template if override else definition.body
        preview_subject, preview_body = render_template_preview(
            provider_key=definition.provider_key,
            event_state=definition.event_state,
            subject_template=subject_template,
            body_template=body_template,
            content_format=content_format,
        )
        result.append(
            {
                'provider_key': definition.provider_key,
                'provider_label': _provider_label(definition.provider_key),
                'event_state': definition.event_state,
                'event_label': definition.event_state.title(),
                'name': override.name if override else definition.name,
                'subject_template': subject_template,
                'body_template': body_template,
                'preview_subject': preview_subject,
                'preview_body': preview_body,
                'content_format': content_format,
                'content_format_label': _FORMAT_LABELS[content_format],
                'allowed_formats': [
                    {'value': value, 'label': _FORMAT_LABELS[value]}
                    for value in _PROVIDER_FORMATS[definition.provider_key]
                ],
                'overridden': override is not None,
                'override_id': override.id if override else None,
            }
        )
    return result


def upsert_template_override(
    *,
    provider_key: str,
    event_state: str,
    name: str,
    subject_template: str | None,
    body_template: str,
    content_format: str,
    actor_user_id: int | None,
) -> AlertNotificationTemplate:
    if provider_key not in _PROVIDER_FORMATS:
        raise ValueError('Unsupported notification provider.')
    if event_state not in {'firing', 'resolved'}:
        raise ValueError('Template event must be Firing or Resolved.')
    normalized_format = str(content_format or 'plain_text').strip().lower()
    if normalized_format not in _PROVIDER_FORMATS[provider_key]:
        allowed = ', '.join(_FORMAT_LABELS[value] for value in _PROVIDER_FORMATS[provider_key])
        raise ValueError(f'{_provider_label(provider_key)} supports these template formats: {allowed}.')
    normalized_name = str(name or '').strip()
    normalized_body = str(body_template or '').strip()
    if not normalized_name or not normalized_body:
        raise ValueError('Template name and body are required.')
    _validate_template(normalized_body, content_format=normalized_format)
    if subject_template:
        _validate_template(subject_template, content_format='plain_text')
    row = (
        AlertNotificationTemplate.query.filter_by(provider_key=provider_key, event_state=event_state)
        .order_by(AlertNotificationTemplate.id.desc())
        .first()
    )
    if row is None:
        row = AlertNotificationTemplate()
        row.provider_key = provider_key
        row.event_state = event_state
    row.name = normalized_name[:160]
    row.subject_template = str(subject_template or '').strip()[:500] or None
    row.body_template = normalized_body
    row.content_format = normalized_format
    row.enabled = True
    row.built_in_override = True
    row.updated_by_user_id = actor_user_id
    return row


def reset_template_override(*, provider_key: str, event_state: str) -> bool:
    if provider_key not in _PROVIDER_FORMATS or event_state not in {'firing', 'resolved'}:
        raise ValueError('Unsupported provider/event template reset target.')
    count = AlertNotificationTemplate.query.filter_by(
        provider_key=provider_key, event_state=event_state
    ).delete(synchronize_session=False)
    return bool(count)



def render_template_preview(
    *,
    provider_key: str,
    event_state: str,
    subject_template: str | None,
    body_template: str,
    content_format: str,
) -> tuple[str, str]:
    if provider_key not in _PROVIDER_FORMATS or event_state not in {'firing', 'resolved'}:
        raise ValueError('Unsupported notification template preview target.')
    normalized_format = str(content_format or 'plain_text').strip().lower()
    if normalized_format not in _PROVIDER_FORMATS[provider_key]:
        raise ValueError(f'{_provider_label(provider_key)} does not support {normalized_format}.')
    _validate_template(body_template, content_format=normalized_format)
    if subject_template:
        _validate_template(subject_template, content_format='plain_text')
    context = _preview_context(event_state)
    subject_source = subject_template or f'[{event_state.upper()}][{{{{ severity }}}}] {{{{ alert_name }}}}'
    subject = _ENV.from_string(subject_source).render(**context).strip()
    renderer = _HTML_ENV if normalized_format == 'html' else _ENV
    body = renderer.from_string(body_template).render(**context).strip()
    if normalized_format == 'html':
        _validate_safe_html(body)
    return subject, body


def _preview_context(event_state: str) -> dict[str, str]:
    return {
        'case_id': 'CASE-DEMO-001',
        'alert_name': 'Kubernetes Pod Restart Threshold',
        'severity': 'CRITICAL' if event_state == 'firing' else 'WARNING',
        'asset_name': 'prod-cluster-01',
        'scope': 'payments / api',
        'namespace': 'payments',
        'summary': 'Pod restart count crossed the governed Rule Catalog threshold.',
        'started_at': '2026-08-22 12:00 UTC',
        'resolved_at': '2026-08-22 12:18 UTC',
        'duration': '18m',
        'evidence_summary': 'restart_count=52, pod=api-7c8d9',
        'resolution_summary': 'Workload stabilized after the remediation was applied.',
        'remediation_steps': '• Reviewed failing container logs\n• Corrected configuration\n• Verified rollout health',
        'verification_evidence': 'Restart count remained stable during post-action verification.',
        'operator_name': 'KAORI Operator',
        'change_reference': 'CHG-DEMO-001',
        'ticket_reference': 'INC-DEMO-001',
        'action_url': '/intelligence/alert-intelligence?tab=' + ('active' if event_state == 'firing' else 'resolved'),
    }

def render_case_message(
    case: AlertCase,
    *,
    provider_key: str,
    event_state: str,
    action_url: str | None,
) -> tuple[str, str, str]:
    definition = _definition(provider_key, event_state)
    override = (
        AlertNotificationTemplate.query.filter_by(
            provider_key=provider_key,
            event_state=event_state,
            enabled=True,
        )
        .order_by(AlertNotificationTemplate.id.desc())
        .first()
    )
    subject_template = override.subject_template if override else definition.subject
    body_template = override.body_template if override else definition.body
    content_format = override.content_format if override else definition.content_format
    context = _template_context(case, action_url=action_url)
    subject = _ENV.from_string(subject_template or _default_title(case, event_state)).render(**context).strip()
    renderer = _HTML_ENV if content_format == 'html' else _ENV
    body = renderer.from_string(body_template).render(**context).strip()
    if content_format == 'html':
        _validate_safe_html(body)
    return subject or _default_title(case, event_state), body, content_format


def _template_context(case: AlertCase, *, action_url: str | None) -> dict[str, str]:
    now = case.closed_at or case.source_resolved_at or case.last_seen_at
    duration_seconds = max(int((now - case.first_seen_at).total_seconds()), 0)
    remediation = '\n'.join(f'• {step}' for step in (case.remediation_steps_json or [])) or '-'
    owner = case.closed_by or case.owner or case.acknowledged_by
    operator_name = str(getattr(owner, 'username', None) or getattr(owner, 'email', None) or 'KAORI')
    evidence = case.evidence_json or {}
    return {
        'case_id': case.public_id,
        'alert_name': case.alert_name,
        'severity': case.severity.upper(),
        'asset_name': case.asset_name,
        'scope': case.namespace or case.target or case.asset_name,
        'namespace': case.namespace or '',
        'summary': case.summary or '-',
        'started_at': _display_datetime(case.first_seen_at),
        'resolved_at': _display_datetime(case.source_resolved_at) if case.source_resolved_at else '-',
        'duration': _duration_label(duration_seconds),
        'evidence_summary': str(evidence.get('summary') or evidence.get('observed') or case.target or '-'),
        'resolution_summary': case.resolution_summary or 'Source recovered; no manual resolution summary was recorded.',
        'remediation_steps': remediation,
        'verification_evidence': case.verification_evidence or 'Source recovery observed by KAORI.',
        'operator_name': operator_name,
        'change_reference': case.change_reference or '-',
        'ticket_reference': case.ticket_reference or '-',
        'action_url': action_url or '',
    }


def _definition(provider_key: str, event_state: str) -> AlertTemplateDefinition:
    for definition in _BUILT_INS:
        if definition.provider_key == provider_key and definition.event_state == event_state:
            return definition
    raise ValueError(f'No Alert Intelligence template is registered for {provider_key}/{event_state}.')


def _validate_template(value: str, *, content_format: str) -> None:
    try:
        _ENV.parse(value)
    except TemplateSyntaxError as exc:
        raise ValueError('Notification template contains invalid template syntax.') from exc
    if content_format == 'html':
        # Static HTML is checked at save time; rendered HTML is checked again before delivery.
        _validate_safe_html(value)


class _SafeHTMLParser(HTMLParser):
    _ALLOWED_TAGS = {
        'p', 'br', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li', 'a', 'code', 'pre',
        'blockquote', 'h1', 'h2', 'h3', 'h4', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span',
    }
    _ALLOWED_ATTRS = {'a': {'href', 'title'}, 'th': {'colspan', 'rowspan'}, 'td': {'colspan', 'rowspan'}}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self._ALLOWED_TAGS:
            raise ValueError(f'HTML template tag <{tag}> is not allowed.')
        allowed = self._ALLOWED_ATTRS.get(tag, set())
        for key, value in attrs:
            if key not in allowed:
                raise ValueError(f'HTML template attribute {key} is not allowed on <{tag}>.')
            if key == 'href' and str(value or '').strip().lower().startswith(('javascript:', 'data:')):
                raise ValueError('HTML template links must use a safe URL scheme.')

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _validate_safe_html(value: str) -> None:
    parser = _SafeHTMLParser(convert_charrefs=True)
    parser.feed(value)
    parser.close()


def _default_title(case: AlertCase, event_state: str) -> str:
    return f'[{event_state.upper()}][{case.severity.upper()}] {case.alert_name}'


def _provider_label(provider_key: str) -> str:
    return {
        'telegram': 'Telegram',
        'email': 'Email',
        'microsoft_teams': 'Microsoft Teams',
    }.get(provider_key, provider_key.replace('_', ' ').title())


def _display_datetime(value) -> str:
    if value is None:
        return '-'
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')


def _duration_label(seconds: int) -> str:
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours, remainder = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {remainder}m'
    days, hours = divmod(hours, 24)
    return f'{days}d {hours}h'
