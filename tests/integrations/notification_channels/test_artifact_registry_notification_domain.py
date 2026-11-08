from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.delivery.notification_channels import forms, service
from app.integrations.delivery.notification_channels.catalog import (
    domain_event_allowed,
    domain_options,
)
from app.integrations.delivery.notification_channels.contracts import NotificationChannelFormInput


@pytest.mark.parametrize(
    ('domain', 'event', 'allowed'),
    [
        ('kubernetes', 'alert_ops.firing', True),
        ('object_storage', 'automation.execution_failed', True),
        ('artifact_registry', 'report.generated', True),
        ('artifact_registry', 'alert_ops.firing', False),
        ('artifact_registry', 'alert_intelligence.active_alert', False),
        ('artifact_registry', 'automation.execution_failed', False),
        ('registry', 'report.generated', False),
        ('registry', 'alert_ops.firing', True),
        ('registry', 'alert_ops.resolved', True),
        ('registry', 'alert_intelligence.active_alert', True),
        ('registry', 'automation.execution_failed', False),
        ('artifact_registry', 'unknown.event', False),
    ],
)
def test_only_source_qualified_domain_events_are_eligible(domain: str, event: str, allowed: bool) -> None:
    assert domain_event_allowed(domain, event) is allowed


def test_registry_report_delivery_is_advertised_with_accurate_scope() -> None:
    options = {item['value']: item for item in domain_options()}
    assert options['artifact_registry'] == {
        'value': 'artifact_registry',
        'label': 'Artifact Registry',
        'hint': 'Report Ready only',
    }
    assert {'kubernetes', 'object_storage'}.issubset(options)
    assert options['registry'] == {
        'value': 'registry',
        'label': 'Registry Alerts',
        'hint': 'Governed AlertCases only',
    }


def _channel_input(*, domains: tuple[str, ...], events: tuple[str, ...]) -> NotificationChannelFormInput:
    return NotificationChannelFormInput(
        name='Registry Reports',
        provider_key='email',
        enabled=True,
        destination='reports@example.invalid',
        credentials={},
        provider_config={},
        minimum_severity='warning',
        domains=domains,
        event_types=events,
        credential_changed=False,
    )


def test_form_requires_at_least_one_approved_use_for_every_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        forms,
        'get_notification_provider',
        lambda _key: SimpleNamespace(form_validator=lambda _data: []),
    )

    assert (
        forms.validate_channel_input(_channel_input(domains=('artifact_registry',), events=('report.generated',))) == []
    )
    rejected = forms.validate_channel_input(
        _channel_input(domains=('artifact_registry',), events=('alert_ops.firing',))
    )
    assert any('artifact_registry' in message for message in rejected)

    mixed_rejected = forms.validate_channel_input(
        _channel_input(domains=('kubernetes', 'artifact_registry'), events=('alert_ops.firing',))
    )
    assert any('artifact_registry' in message for message in mixed_rejected)

    assert (
        forms.validate_channel_input(
            _channel_input(
                domains=('kubernetes', 'artifact_registry'),
                events=('alert_ops.firing', 'report.generated'),
            )
        )
        == []
    )


def test_delivery_matcher_preserves_report_only_boundary_even_for_stale_policy() -> None:
    channel = SimpleNamespace(
        enabled=True,
        lifecycle_state='active',
        configured=True,
        test_status='success',
        domains=['artifact_registry', 'registry'],
        event_types=['report.generated', 'alert_ops.firing'],
        minimum_severity='info',
    )

    assert service._channel_matches_event(
        channel, domain='artifact_registry', event_type='report.generated', severity='info'
    )
    assert not service._channel_matches_event(
        channel, domain='artifact_registry', event_type='alert_ops.firing', severity='warning'
    )
    assert service._channel_matches_event(channel, domain='registry', event_type='alert_ops.firing', severity='warning')
    assert not service._channel_matches_event(
        channel, domain='registry', event_type='report.generated', severity='warning'
    )
    channel.domains = ['artifact_registry']
    assert not service._channel_matches_event(
        channel, domain='registry', event_type='alert_ops.firing', severity='warning'
    )
    channel.domains = ['artifact_registry', 'registry']
    channel.enabled = False
    assert not service._channel_matches_event(
        channel, domain='artifact_registry', event_type='report.generated', severity='info'
    )
