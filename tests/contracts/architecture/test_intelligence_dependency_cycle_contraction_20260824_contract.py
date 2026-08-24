import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_cluster_lifecycle_uses_shared_alert_case_source_state_boundary() -> None:
    cluster = read('app/kubernetes/cluster/service.py')
    shared = read('app/common/alert_case_source_state.py')

    assert 'from app.common.alert_case_source_state import mark_asset_alert_cases_source_unknown' in cluster
    assert 'app.intelligence.alert_intelligence.case_state' not in cluster
    assert 'def mark_asset_alert_cases_source_unknown(' in shared
    assert "reason: str = 'source_deleted'" in shared


def test_provider_resolver_adapter_depends_on_shared_contract_not_intelligence_domain() -> None:
    adapter = read('app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/resolver_adapter.py')
    bootstrap = read('app/integrations/resolver_bootstrap.py')
    shared_contract = read('app/common/resolver_contracts.py')
    shared_registry = read('app/common/resolver_registry.py')

    assert 'from app.common.resolver_contracts import (' in adapter
    assert 'from app.common.resolver_contracts import ResolverError' in bootstrap
    assert 'from app.common.resolver_registry import ResolverRegistry' in bootstrap
    assert 'app.intelligence.resolver.contracts' not in adapter
    assert 'app.intelligence.resolver.registry' not in bootstrap
    assert 'class ResolverAdapter(Protocol):' in shared_contract
    assert 'class ResolverRegistry:' in shared_registry


def test_resolver_compatibility_surfaces_reexport_shared_contract_identity() -> None:
    contracts = read('app/intelligence/resolver/contracts.py')
    registry = read('app/intelligence/resolver/registry.py')

    assert 'from app.common.resolver_contracts import (' in contracts
    assert 'from app.common.resolver_registry import ResolverDescriptor, ResolverRegistry' in registry
    assert 'post-action verification-capable adapters' in registry


def test_recommendation_alert_commands_are_owned_by_alert_intelligence_logical_domain() -> None:
    verifier = read('scripts/verify_architecture_boundaries.py')
    assert "('app.intelligence.recommendation_alert_commands', 'alert_intelligence')" in verifier


def test_architecture_debt_envelopes_are_not_expanded_for_intelligence() -> None:
    baseline = json.loads(read('docs/architecture/architecture-debt-baseline.json'))
    envelopes = [set(item['domains']) for item in baseline['cycle_envelopes']]

    forbidden_expansion = {'alert_intelligence', 'analytics', 'intelligence', 'resolver'}
    assert all(not (envelope & forbidden_expansion) for envelope in envelopes)
