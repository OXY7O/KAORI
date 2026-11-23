"""Provider-qualified Registry Metrics Source queries (#5125)."""

from pathlib import Path

import pytest

from app.integrations.registry.metric_queries import qualified_registry_metric_query
from app.models.integration import IntegrationInstance

ROOT = Path(__file__).resolve().parents[3]


def _instance(provider: str, *, integration_type: str = 'registry') -> IntegrationInstance:
    instance = IntegrationInstance()
    instance.integration_type = integration_type
    instance.provider_key = provider
    return instance


def test_harbor_preserves_registered_semantic_query_profile() -> None:
    reference = qualified_registry_metric_query(_instance('harbor'), 'registry.health')

    assert reference.key == 'registry.health'
    assert reference.profile_key == 'registry-harbor-v1'
    assert str(reference) == 'max(harbor_health)'


def test_unknown_registry_provider_never_receives_harbor_query() -> None:
    with pytest.raises(LookupError, match='No qualified operational metrics query profile'):
        qualified_registry_metric_query(_instance('unqualified_registry'), 'registry.health')


def test_wrong_domain_cannot_resolve_registry_metrics() -> None:
    with pytest.raises(LookupError, match='requires a Registry integration instance'):
        qualified_registry_metric_query(_instance('harbor', integration_type='object_storage'), 'registry.health')


def test_unsupported_semantic_key_does_not_silently_map_to_harbor_metric() -> None:
    with pytest.raises(LookupError, match='not registered'):
        qualified_registry_metric_query(_instance('harbor'), 'registry.unsupported.metric')


def test_generic_registry_analytics_does_not_import_harbor_profile() -> None:
    for path in (
        'app/artifact_registry/analytics.py',
        'app/artifact_registry/analytics_history.py',
    ):
        content = (ROOT / path).read_text(encoding='utf-8')
        assert 'qualified_registry_metric_query' in content
        assert 'registry_harbor_v1' not in content

    resolver = (ROOT / 'app/integrations/registry/metric_queries.py').read_text(encoding='utf-8')
    assert "    'harbor': harbor_registry_query," in resolver
