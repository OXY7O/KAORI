from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.alertmanager.bindings import create_or_update_binding  # noqa: E402
from app.alertmanager.consumer import list_alerts_for_scope  # noqa: E402
from app.integrations.alertmanager.exceptions import AlertmanagerConnectionError  # noqa: E402
from app.alertmanager.forms import AlertmanagerBindingForm, AlertmanagerInstanceForm  # noqa: E402
from app.alertmanager.resolver import resolve_alertmanager_sources  # noqa: E402
from app.alertmanager.service import save_alertmanager_instance  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Cluster  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _cluster() -> Cluster:
    cluster = Cluster()
    cluster.name = 'Resolver Cluster'
    cluster.environment = 'production'
    db.session.add(cluster)
    db.session.flush()
    return cluster


def _instance(name: str, *, role: str, cluster_id: str, priority: int = 100):
    instance = save_alertmanager_instance(
        form=AlertmanagerInstanceForm(
            name=name,
            description=None,
            deployment_type='shared',
            endpoint=f'https://{name.lower().replace(" ", "-")}.example.test',
            auth_type='none',
            username=None,
            password=None,
            bearer_token=None,
            timeout=5,
            verify_ssl=True,
            enabled=True,
        )
    )
    binding = create_or_update_binding(
        instance=instance,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster_id,
            binding_role=role,
            priority=priority,
            enabled=True,
            selector_label='cluster',
            selector_value=cluster_id,
        ),
    )
    binding.validation_status = 'ready'
    db.session.commit()
    return instance


def test_healthy_secondary_is_preferred_over_unhealthy_primary(app) -> None:
    cluster = _cluster()
    primary = _instance('Primary Source', role='primary', cluster_id=cluster.id)
    secondary = _instance('Secondary Source', role='secondary', cluster_id=cluster.id)

    primary.readiness_status = 'ready'
    primary.last_status = 'error'
    primary.capabilities = ['alerts_v2']
    secondary.readiness_status = 'ready'
    secondary.last_status = 'connected'
    secondary.capabilities = ['alerts_v2']
    db.session.commit()

    resolution = resolve_alertmanager_sources(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        required_capabilities=('alerts_v2',),
    )

    assert resolution.selected is not None
    assert resolution.selected.instance.id == secondary.id
    assert resolution.selected.binding.binding_role == 'secondary'
    assert resolution.candidates[1].instance.id == primary.id
    assert resolution.candidates[1].operational_state == 'unhealthy'


def test_source_missing_required_capability_is_rejected(app) -> None:
    cluster = _cluster()
    primary = _instance('Primary Source', role='primary', cluster_id=cluster.id)
    secondary = _instance('Silence Source', role='secondary', cluster_id=cluster.id)

    primary.readiness_status = 'ready'
    primary.last_status = 'connected'
    primary.capabilities = ['alerts_v2']
    secondary.readiness_status = 'ready'
    secondary.last_status = 'connected'
    secondary.capabilities = ['alerts_v2', 'silences_v2']
    db.session.commit()

    resolution = resolve_alertmanager_sources(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        required_capabilities=('silences_v2',),
    )

    assert resolution.selected is not None
    assert resolution.selected.instance.id == secondary.id
    rejected = next(candidate for candidate in resolution.candidates if candidate.instance.id == primary.id)
    assert rejected.eligible is False
    assert rejected.missing_capabilities == ('silences_v2',)


def test_runtime_failure_falls_through_and_records_selection_trace(app, monkeypatch) -> None:
    cluster = _cluster()
    primary = _instance('Primary Source', role='primary', cluster_id=cluster.id)
    secondary = _instance('Secondary Source', role='secondary', cluster_id=cluster.id)
    for source in (primary, secondary):
        source.readiness_status = 'ready'
        source.last_status = 'connected'
        source.capabilities = ['alerts_v2']
    db.session.commit()

    class FakeClient:
        def __init__(self, name: str) -> None:
            self.name = name

        def get_alerts(self, **_kwargs: Any) -> list[dict[str, Any]]:
            if self.name == 'Primary Source':
                raise AlertmanagerConnectionError('temporary provider failure')
            return [{
                'labels': {'alertname': 'FallbackWorked'},
                'annotations': {},
                'status': {'state': 'active', 'silencedBy': [], 'inhibitedBy': []},
                'startsAt': '2026-07-18T00:00:00Z',
                'fingerprint': 'fallback-1',
            }]

    monkeypatch.setattr(
        'app.integrations.alertmanager.reader.build_client',
        lambda source: FakeClient(source.name),
    )
    result = list_alerts_for_scope(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
    )

    assert result['connected'] is True
    assert result['fallback_used'] is True
    assert result['source_instance_id'] == secondary.id
    assert result['selected_source']['instance_id'] == secondary.id
    assert result['source_errors']


def test_unobserved_capabilities_remain_compatible_during_cutover(app) -> None:
    cluster = _cluster()
    source = _instance('Migrated Source', role='primary', cluster_id=cluster.id)
    source.readiness_status = 'ready'
    source.last_status = 'connected'
    source.capabilities = None
    db.session.commit()

    resolution = resolve_alertmanager_sources(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        required_capabilities=('alerts_v2',),
    )

    assert resolution.selected is not None
    assert resolution.selected.instance.id == source.id
    assert resolution.selected.capability_state == 'unknown'


def test_instance_context_exposes_effective_source_decision_trace(app) -> None:
    from app.alertmanager.presentation import build_instance_context

    cluster = _cluster()
    primary = _instance('Context Primary', role='primary', cluster_id=cluster.id)
    secondary = _instance('Context Secondary', role='secondary', cluster_id=cluster.id)

    primary.readiness_status = 'ready'
    primary.last_status = 'connected'
    primary.capabilities = ['alerts_v2']
    secondary.readiness_status = 'ready'
    secondary.last_status = 'connected'
    secondary.capabilities = ['alerts_v2', 'silences_v2']
    db.session.commit()

    context = build_instance_context(primary)
    scope = context['source_resolution_rows'][0]

    assert scope['scope_label'] == cluster.name
    assert scope['alerts']['selected_instance_id'] == primary.id
    assert scope['alerts']['current_instance_selected'] is True
    assert scope['silences']['selected_instance_id'] == secondary.id
    primary_silence_candidate = next(
        item
        for item in scope['silences']['candidates']
        if item['instance_id'] == primary.id
    )
    assert primary_silence_candidate['eligible'] is False
    assert primary_silence_candidate['missing_capability_labels'] == ['Silences API']
