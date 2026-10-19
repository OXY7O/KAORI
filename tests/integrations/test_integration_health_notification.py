from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.integrations.runtime import notifications

ROOT = Path(__file__).resolve().parents[2]


def _observation(
    *,
    health_status: str,
    observation_id: int = 7,
    integration_instance_id: int | None = 12,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=observation_id,
        integration_instance_id=integration_instance_id,
        integration_type='registry',
        provider_key='harbor',
        instance_id='12',
        instance_name='Harbor UAT',
        health_status=health_status,
        readiness='degraded',
        message='contains sensitive provider exception and credential value',
        diagnostics=[{'detail': 'password=secret'}],
        capability_snapshot={'token': 'must-not-leak'},
    )


@pytest.mark.parametrize(
    ('previous', 'current', 'notify'),
    [
        ('healthy', 'degraded', True),
        ('healthy', 'unhealthy', True),
        ('degraded', 'unhealthy', False),
        ('unhealthy', 'unhealthy', False),
        ('degraded', 'healthy', False),
        ('healthy', 'healthy', False),
    ],
)
def test_health_degradation_requires_a_new_observed_transition(previous: str, current: str, notify: bool) -> None:
    before = _observation(health_status=previous, observation_id=6)
    after = _observation(health_status=current)
    assert notifications.is_health_degradation(before, after) is notify
    assert not notifications.is_health_degradation(None, after)


def test_notification_contract_uses_committed_identity_and_redacts_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notifications, 'current_app', SimpleNamespace(config={}))
    row = _observation(health_status='unhealthy')
    event = notifications.build_integration_health_event(row)
    assert event.domain == 'integrations'
    assert event.event_type == 'integrations.health_degraded'
    assert event.asset_type == 'integration_instance'
    assert event.asset_key == '12'
    assert event.event_key == 'integrations.health_degraded:7'
    assert event.message.severity == 'critical'
    assert event.message.action_url == '/integrations'
    assert 'password=secret' not in str(event)
    assert 'contains sensitive' not in str(event)
    assert 'must-not-leak' not in str(event)
    assert 'diagnostics' not in str(event.payload)


def test_only_persisted_canonical_unhealthy_observation_can_be_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notifications, 'current_app', SimpleNamespace(config={}))
    with pytest.raises(ValueError, match='degraded/unhealthy'):
        notifications.build_integration_health_event(_observation(health_status='healthy'))
    with pytest.raises(ValueError, match='persisted canonical'):
        notifications.build_integration_health_event(
            _observation(health_status='unhealthy', integration_instance_id=None)
        )


def test_notification_enqueue_is_after_source_commit_and_delivery_refuses_stale_instance() -> None:
    repository = (ROOT / 'app/integrations/runtime/repository.py').read_text()
    task = (ROOT / 'app/integrations/runtime/notification_delivery_task.py').read_text()
    config = (ROOT / 'app/config/default.py').read_text()
    assert repository.index('db.session.commit()\n    if integration_instance_id') < repository.index(
        'cast(Task, dispatch_integration_health_notification).apply_async('
    )
    assert "instance.lifecycle_status != 'active'" in task
    assert 'or not instance.enabled' in task
    assert 'latest.id != observation.id' in task
    assert 'if not is_health_degradation(previous, observation):' in task
    assert "'app.integrations.runtime.tasks.dispatch_integration_health_notification'" in config
