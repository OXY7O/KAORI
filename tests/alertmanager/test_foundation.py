from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.alertmanager.bindings import create_or_update_binding  # noqa: E402
from app.alertmanager.consumer import get_scope_status, list_alerts_for_scope  # noqa: E402
from app.alertmanager.forms import AlertmanagerBindingForm, AlertmanagerInstanceForm  # noqa: E402
from app.alertmanager.service import (  # noqa: E402
    create_alertmanager_instance,
    materialize_legacy_cluster_config,
    save_alertmanager_instance,
)
from app.extensions import db  # noqa: E402
from app.models import AlertmanagerInstance, Cluster  # noqa: E402
from app.models.integration import IntegrationBinding  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _instance_form(**overrides: Any) -> AlertmanagerInstanceForm:
    values: dict[str, Any] = {
        'name': 'Central Alertmanager',
        'description': 'Shared alert source.',
        'deployment_type': 'shared',
        'endpoint': 'https://alertmanager.example.test',
        'auth_type': 'basic',
        'username': 'kaori',
        'password': 'initial-secret',
        'bearer_token': None,
        'timeout': 5,
        'verify_ssl': True,
        'enabled': True,
    }
    values.update(overrides)
    return AlertmanagerInstanceForm(**values)


def _cluster(name: str = 'Cluster A') -> Cluster:
    cluster = Cluster(
        name=name,
        environment='production',
    )
    db.session.add(cluster)
    db.session.flush()
    return cluster


def test_instance_secret_is_preserved_when_edit_field_is_blank(app) -> None:
    instance = save_alertmanager_instance(form=_instance_form())
    instance_id = instance.id

    updated = save_alertmanager_instance(
        instance=instance,
        form=_instance_form(
            description='Updated description.',
            password=None,
        ),
    )

    assert updated.id == instance_id
    assert updated.password == 'initial-secret'
    assert updated.readiness_status == 'validation_required'
    assert updated.validation_message is not None



def test_instance_endpoint_rejects_embedded_credentials_or_query(app) -> None:
    with pytest.raises(ValueError, match='Do not embed credentials'):
        save_alertmanager_instance(
            form=_instance_form(endpoint='https://user:secret@alertmanager.example.test'),
        )
    with pytest.raises(ValueError, match='must not include query parameters'):
        save_alertmanager_instance(
            form=_instance_form(endpoint='https://alertmanager.example.test?token=secret'),
        )
    assert AlertmanagerInstance.query.count() == 0


def test_scope_status_exposes_only_sanitized_console_endpoint(app) -> None:
    cluster = _cluster()
    instance = save_alertmanager_instance(
        form=_instance_form(
            auth_type='none',
            username=None,
            password=None,
            endpoint='https://alertmanager.example.test/proxy',
        )
    )
    binding = create_or_update_binding(
        instance=instance,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
            binding_role='primary',
            priority=100,
            enabled=True,
            selector_label='cluster',
            selector_value=cluster.id,
        ),
    )
    binding.validation_status = 'ready'
    db.session.commit()

    status = get_scope_status(scope_type='kubernetes_cluster', scope_key=cluster.id)
    assert status['endpoint'] == 'https://alertmanager.example.test/proxy'

def test_scope_resolver_reads_canonical_alerts_from_bound_instance(app, monkeypatch) -> None:
    cluster = _cluster()
    instance = save_alertmanager_instance(form=_instance_form(auth_type='none', username=None, password=None))
    instance.readiness_status = 'ready'
    db.session.commit()
    binding = create_or_update_binding(
        instance=instance,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
            binding_role='primary',
            priority=100,
            enabled=True,
            selector_label='cluster',
            selector_value=cluster.id,
        ),
    )
    binding.validation_status = 'ready'
    db.session.commit()

    class FakeClient:
        def get_alerts(self, **_kwargs: Any) -> list[dict[str, Any]]:
            return [
                {
                    'labels': {
                        'alertname': 'KubePodCrashLooping',
                        'severity': 'warning',
                        'namespace': 'payments',
                        'pod': 'api-0',
                    },
                    'annotations': {'summary': 'Pod is restarting.'},
                    'status': {'state': 'active', 'silencedBy': [], 'inhibitedBy': []},
                    'startsAt': '2026-07-18T00:00:00Z',
                    'endsAt': '2026-07-18T01:00:00Z',
                    'fingerprint': 'abc123',
                }
            ]

    monkeypatch.setattr('app.integrations.alertmanager.reader.build_client', lambda _source: FakeClient())
    result = list_alerts_for_scope(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
    )

    assert result['connected'] is True
    assert result['source_instance_id'] == instance.id
    assert result['source_instance_name'] == instance.name
    assert result['alerts'][0]['alert_name'] == 'KubePodCrashLooping'
    assert result['alerts'][0]['labels']['namespace'] == 'payments'
    assert 'resource_type' not in result['alerts'][0]


def test_only_one_primary_source_is_allowed_per_scope(app) -> None:
    cluster = _cluster()
    first = save_alertmanager_instance(form=_instance_form(name='Primary Alertmanager'))
    second = save_alertmanager_instance(form=_instance_form(name='Secondary Alertmanager'))
    primary = AlertmanagerBindingForm(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        binding_role='primary',
        priority=100,
        enabled=True,
        selector_label='cluster',
        selector_value=cluster.id,
    )
    create_or_update_binding(instance=first, form=primary)

    with pytest.raises(ValueError, match='already has a primary'):
        create_or_update_binding(instance=second, form=primary)

    create_or_update_binding(
        instance=second,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
            binding_role='fallback',
            priority=200,
            enabled=True,
            selector_label='cluster',
            selector_value=cluster.id,
        ),
    )
    assert IntegrationBinding.query.count() == 2



def test_instance_and_initial_binding_are_created_atomically(app) -> None:
    cluster = _cluster()
    existing = save_alertmanager_instance(form=_instance_form(name='Existing Primary'))
    primary = AlertmanagerBindingForm(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        binding_role='primary',
        priority=100,
        enabled=True,
        selector_label='cluster',
        selector_value=cluster.id,
    )
    create_or_update_binding(instance=existing, form=primary)

    with pytest.raises(ValueError, match='already has a primary'):
        create_alertmanager_instance(
            form=_instance_form(name='Rejected New Source'),
            initial_binding=primary,
        )

    assert AlertmanagerInstance.query.filter_by(name='Rejected New Source').one_or_none() is None
    assert AlertmanagerInstance.query.count() == 1
    assert IntegrationBinding.query.count() == 1

def test_legacy_cluster_bookmark_helper_resolves_canonical_binding(app) -> None:
    cluster = _cluster('Legacy Cluster')
    source = save_alertmanager_instance(
        form=_instance_form(
            name='Canonical Alertmanager',
            deployment_type='cluster_managed',
            endpoint='http://canonical-alertmanager:9093',
            auth_type='none',
            username=None,
            password=None,
        )
    )
    binding = create_or_update_binding(
        instance=source,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
            binding_role='primary',
            priority=100,
            enabled=True,
            selector_label='cluster',
            selector_value=cluster.id,
        ),
    )
    binding.validation_status = 'ready'
    db.session.commit()

    instance = materialize_legacy_cluster_config(cluster.id)
    assert instance is not None
    assert instance.id == source.id
    assert instance.endpoint == 'http://canonical-alertmanager:9093'
    assert len(instance.integration_instance.bindings) == 1
    assert instance.integration_instance.bindings[0].asset_type == 'kubernetes_cluster'
    assert instance.integration_instance.bindings[0].asset_key == cluster.id
    assert AlertmanagerInstance.query.count() == 1
