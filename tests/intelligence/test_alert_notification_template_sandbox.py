"""Operator alert notification templates must fail closed in a Jinja sandbox."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.intelligence.alert_intelligence import templates


@pytest.mark.parametrize(
    ('provider_key', 'content_format', 'body_template'),
    [
        ('email', 'plain_text', 'Alert {{ alert_name }}{% if namespace %} / {{ namespace }}{% endif %}'),
        ('microsoft_teams', 'markdown', '**{{ alert_name }}**{% if namespace %} {{ namespace }}{% endif %}'),
        ('telegram', 'html', '<b>{{ alert_name }}</b>{% if namespace %}<em>{{ namespace }}</em>{% endif %}'),
    ],
)
def test_allowed_variables_and_conditionals_still_render(
    provider_key: str, content_format: str, body_template: str
) -> None:
    subject, body = templates.render_template_preview(
        provider_key=provider_key,
        event_state='firing',
        subject_template='[{{ severity }}] {{ alert_name }}',
        body_template=body_template,
        content_format=content_format,
    )
    assert subject == '[CRITICAL] Kubernetes Pod Restart Threshold'
    assert 'Kubernetes Pod Restart Threshold' in body
    assert 'payments' in body


def test_html_escapes_context_and_plain_text_keeps_existing_output() -> None:
    source = '<b>{{ alert_name }}</b>'
    value = '<untrusted>'
    assert templates._HTML_ENV.from_string(source).render(alert_name=value) == (
        '<b>&lt;untrusted&gt;</b>'
    )
    assert templates._ENV.from_string(source).render(alert_name=value) == (
        '<b><untrusted></b>'
    )


@pytest.mark.parametrize('field', ['subject', 'body'])
@pytest.mark.parametrize('content_format', ['plain_text', 'html'])
def test_preview_denies_unsafe_attribute_access(field: str, content_format: str) -> None:
    # Benign attribute probe: no dangerous process or filesystem action.
    forbidden = "{{ 'value'.__class__ }}"
    kwargs = {
        'provider_key': 'email',
        'event_state': 'firing',
        'subject_template': forbidden if field == 'subject' else '{{ severity }}',
        'body_template': forbidden if field == 'body' else '<b>{{ alert_name }}</b>',
        'content_format': content_format,
    }
    with pytest.raises(ValueError, match='unsupported expression'):
        templates.render_template_preview(**kwargs)


def test_save_rejects_unsafe_override_before_database_mutation() -> None:
    with pytest.raises(ValueError, match='unsupported expression'):
        templates.upsert_template_override(
            provider_key='email',
            event_state='firing',
            name='Unsafe template',
            subject_template=None,
            body_template="{{ 'value'.__class__ }}",
            content_format='plain_text',
            actor_user_id=1,
        )


def _override(monkeypatch: pytest.MonkeyPatch, *, subject: str | None, body: str) -> None:
    fake_model = MagicMock()
    fake_model.query.filter_by.return_value.order_by.return_value.first.return_value = (
        SimpleNamespace(
            subject_template=subject,
            body_template=body,
            content_format='plain_text',
        )
    )
    monkeypatch.setattr(templates, 'AlertNotificationTemplate', fake_model)
    monkeypatch.setattr(
        templates,
        '_template_context',
        lambda case, *, action_url: {'severity': 'WARNING', 'alert_name': case.alert_name},
    )


@pytest.mark.parametrize('field', ['subject', 'body'])
def test_delivery_denies_unsafe_saved_override(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    forbidden = "{{ 'value'.__class__ }}"
    _override(
        monkeypatch,
        subject=forbidden if field == 'subject' else '{{ severity }}',
        body=forbidden if field == 'body' else 'Hello {{ alert_name }}',
    )
    case = SimpleNamespace(severity='warning', alert_name='Known case')
    with pytest.raises(ValueError, match='unsupported expression'):
        templates.render_case_message(
            case, provider_key='email', event_state='firing', action_url=None
        )


def test_delivery_treats_fallback_title_as_literal_case_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    literal = "{{ 'value'.__class__ }}"
    _override(monkeypatch, subject=None, body='Alert {{ alert_name }}')
    case = SimpleNamespace(severity='warning', alert_name=literal)
    subject, body, content_format = templates.render_case_message(
        case, provider_key='email', event_state='firing', action_url=None
    )
    assert subject == f'[FIRING][WARNING] {literal}'
    assert body == f'Alert {literal}'
    assert content_format == 'plain_text'
