"""Harbor runtime rows use persisted evidence and canonical detail identity."""

from types import SimpleNamespace
from unittest.mock import patch

from app.integrations.registry.providers.harbor import runtime_overview


def test_harbor_runtime_row_is_committed_and_resolves_distinct_ids():
    canonical = SimpleNamespace(
        id=72,
        name='Harbor A',
        provider_key='harbor',
        adapter_key='harbor_api_v2',
        enabled=True,
        lifecycle_status='active',
        bindings=[],
    )
    record = SimpleNamespace(
        id=3,
        integration_instance=canonical,
        readiness_status='ready',
        capability_profile='harbor',
        compatibility_profile=None,
        capabilities=['health'],
        last_status='connected',
        last_checked_at=None,
        last_validated_at=None,
        validation_message=None,
        last_error=None,
    )
    with patch.object(runtime_overview, 'provider_kind', return_value=SimpleNamespace(key='harbor', label='Harbor')):
        row = runtime_overview._runtime_row(record, None)
        assert row['instance_id'] == '3'
        assert row['detail_key'] == 'registry:72'
        assert row['readiness'] == 'ready'
        assert row['health_status'] == 'not_observed'
        canonical.enabled = False
        assert runtime_overview._runtime_row(record, None)['readiness'] == 'blocked'
