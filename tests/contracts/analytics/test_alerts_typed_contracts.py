from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app' / 'analytics' / 'alerts'
CONTRACTS = ALERTS / 'contracts.py'
SOURCES = ALERTS / 'sources.py'
SNAPSHOTS = ALERTS / 'snapshots.py'
HEALTH = ALERTS / 'health.py'
ROUTING = ALERTS / 'routing.py'
SILENCES = ALERTS / 'silences.py'
INHIBITION = ALERTS / 'inhibition.py'
OWNERSHIP = ALERTS / 'ownership.py'
READINESS = ALERTS / 'readiness.py'
SIGNALS = ALERTS / 'signals.py'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

TYPED_CONTRACTS = {
    'AlertClusterSignalComparisonRow',
    'AlertIncidentReadinessCheck',
    'AlertIncidentReadinessSummary',
    'AlertInhibitionItem',
    'AlertInhibitionSummary',
    'AlertIntegrationStatus',
    'AlertIntegrationStatusMap',
    'AlertMissingMetadataItem',
    'AlertOwnershipGroup',
    'AlertOwnershipSummary',
    'AlertResourceLink',
    'AlertResourceLinks',
    'AlertRoutingGroup',
    'AlertRoutingSummary',
    'AlertSelectedClusterSignalOverview',
    'AlertSignalBars',
    'AlertSignalInsight',
    'AlertSignalPriority',
    'AlertRunbookItem',
    'AlertSilenceApiStatus',
    'AlertSilenceItem',
    'AlertSilenceMatcher',
    'AlertSilenceSummary',
    'AlertSourceHealthCheck',
    'AlertSourceHealthSummary',
    'AlertSourceStatus',
    'AlertsSnapshot',
    'NormalizedAlert',
}

TYPED_CONSUMERS = {
    'health.py',
    'inhibition.py',
    'ownership.py',
    'routing.py',
    'signals.py',
    'silences.py',
    'snapshots.py',
    'sources.py',
}


def _function_return_annotations(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))

    return {
        node.name: ast.unparse(node.returns)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.returns is not None
    }


def _load_contracts_module():
    spec = importlib.util.spec_from_file_location(
        'kaori_alert_contracts_runtimecheck',
        CONTRACTS,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _typed_dict_keys(class_name: str) -> tuple[set[str], set[str]]:
    contract = getattr(_load_contracts_module(), class_name)
    return set(contract.__required_keys__), set(contract.__optional_keys__)


def _return_dictionary_keys(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue

        keys = {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if keys:
            return keys

    raise AssertionError(f'No literal dictionary return found for {function_name}')


def _appended_dictionary_keys(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    for node in ast.walk(function):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'append'
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Dict)
        ):
            continue

        keys = {
            key.value
            for key in node.args[0].keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if keys:
            return keys

    raise AssertionError(f'No appended literal dictionary found for {function_name}')


def _assigned_subscript_keys(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    return {
        target.slice.value
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and isinstance(target.slice.value, str)
    }


def _nested_dictionary_keys_from_return(
    path: Path,
    function_name: str,
    key_name: str,
) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue

        for key, value in zip(node.value.keys, node.value.values, strict=True):
            if not (
                isinstance(key, ast.Constant)
                and key.value == key_name
                and isinstance(value, ast.Dict)
            ):
                continue

            return {
                nested_key.value
                for nested_key in value.keys
                if isinstance(nested_key, ast.Constant) and isinstance(nested_key.value, str)
            }

    raise AssertionError(f'No nested dictionary {key_name!r} found for {function_name}')


def test_alert_contracts_are_explicit_typed_dictionaries() -> None:
    tree = ast.parse(CONTRACTS.read_text(encoding='utf-8'))
    typed_dicts = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(ast.unparse(base) == 'TypedDict' for base in node.bases)
    }
    typed_dicts.update(
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == 'TypedDict'
        for target in node.targets
        if isinstance(target, ast.Name)
    )
    aliases = {
        node.name.id
        for node in tree.body
        if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name)
    }

    assert TYPED_CONTRACTS <= typed_dicts
    assert 'AlertLoadResult' in aliases


def test_source_boundary_returns_canonical_alert_contracts() -> None:
    annotations = _function_return_annotations(SOURCES)
    source = SOURCES.read_text(encoding='utf-8')

    assert annotations['build_empty_source_status'] == 'AlertSourceStatus'
    assert annotations['normalize_alertmanager_item'] == 'NormalizedAlert'
    assert annotations['normalize_prometheus_alert'] == 'NormalizedAlert'
    assert annotations['load_alertmanager_alerts'] == 'AlertLoadResult'
    assert annotations['load_prometheus_alerts'] == 'AlertLoadResult'
    assert annotations['load_alerts_by_source'] == 'AlertLoadResult'
    assert 'tuple[list[dict[str, Any]], dict[str, Any]]' not in source


def test_snapshot_boundary_has_an_explicit_contract() -> None:
    annotations = _function_return_annotations(SNAPSHOTS)
    snapshot_source = CONTRACTS.read_text(encoding='utf-8')

    assert annotations['get_alerts_snapshot'] == 'AlertsSnapshot'
    assert annotations['_empty_alerts_snapshot'] == 'AlertsSnapshot'
    assert 'source_health: AlertSourceHealthSummary' in snapshot_source
    assert 'routing_summary: AlertRoutingSummary' in snapshot_source
    assert 'silence_summary: AlertSilenceSummary' in snapshot_source
    assert 'inhibition_summary: AlertInhibitionSummary' in snapshot_source
    assert 'ownership_summary: AlertOwnershipSummary' in snapshot_source
    assert 'incident_readiness: AlertIncidentReadinessSummary' in snapshot_source
    assert 'priority: AlertSignalPriority' in snapshot_source
    assert 'insight: AlertSignalInsight' in snapshot_source


def test_health_and_routing_boundaries_use_focused_contracts() -> None:
    health_annotations = _function_return_annotations(HEALTH)
    routing_annotations = _function_return_annotations(ROUTING)

    assert health_annotations['build_prometheus_status'] == 'AlertIntegrationStatus'
    assert health_annotations['build_alertmanager_integration_status'] == 'AlertIntegrationStatus'
    assert health_annotations['build_integration_status'] == 'AlertIntegrationStatusMap'
    assert health_annotations['build_source_health'] == 'AlertSourceHealthSummary'
    assert routing_annotations['build_count_groups'] == 'list[AlertRoutingGroup]'
    assert routing_annotations['build_routing_summary'] == 'AlertRoutingSummary'
    assert routing_annotations['build_empty_routing_summary'] == 'AlertRoutingSummary'


def test_silence_and_inhibition_boundaries_use_focused_contracts() -> None:
    silence_annotations = _function_return_annotations(SILENCES)
    inhibition_annotations = _function_return_annotations(INHIBITION)

    assert silence_annotations['load_alertmanager_silences'] == (
        'tuple[list[dict[str, Any]], AlertSilenceApiStatus]'
    )
    assert silence_annotations['normalize_silence_matchers'] == 'list[AlertSilenceMatcher]'
    assert silence_annotations['build_silence_summary'] == 'AlertSilenceSummary'
    assert silence_annotations['build_empty_silence_summary'] == 'AlertSilenceSummary'
    assert inhibition_annotations['build_inhibition_summary'] == 'AlertInhibitionSummary'


def test_ownership_and_readiness_boundaries_use_focused_contracts() -> None:
    ownership_annotations = _function_return_annotations(OWNERSHIP)
    readiness_annotations = _function_return_annotations(READINESS)
    readiness_source = READINESS.read_text(encoding='utf-8')

    assert ownership_annotations['build_ownership_summary'] == 'AlertOwnershipSummary'
    assert ownership_annotations['build_empty_ownership_summary'] == 'AlertOwnershipSummary'
    assert readiness_annotations['build_incident_readiness'] == 'AlertIncidentReadinessSummary'
    assert readiness_annotations['build_empty_incident_readiness'] == 'AlertIncidentReadinessSummary'
    assert 'source_health: AlertSourceHealthSummary' in readiness_source
    assert 'routing_summary: AlertRoutingSummary' in readiness_source
    assert 'silence_summary: AlertSilenceSummary' in readiness_source
    assert 'inhibition_summary: AlertInhibitionSummary' in readiness_source
    assert 'ownership_summary: AlertOwnershipSummary' in readiness_source


def test_selected_cluster_signal_boundary_uses_focused_contracts() -> None:
    signal_annotations = _function_return_annotations(SIGNALS)
    readiness_source = READINESS.read_text(encoding='utf-8')

    assert signal_annotations['build_selected_cluster_signal_overview'] == (
        'AlertSelectedClusterSignalOverview'
    )
    assert 'signal_overview: AlertSelectedClusterSignalOverview' in readiness_source


def test_multi_cluster_and_resource_link_boundaries_use_focused_contracts() -> None:
    signal_annotations = _function_return_annotations(SIGNALS)

    assert signal_annotations['build_cluster_signal_overview'] == (
        'list[AlertClusterSignalComparisonRow]'
    )
    assert signal_annotations['build_resource_links'] == 'AlertResourceLinks'


def test_alert_consumers_use_the_canonical_types() -> None:
    offenders: list[str] = []

    for filename in sorted(TYPED_CONSUMERS):
        source = (ALERTS / filename).read_text(encoding='utf-8')
        if filename != 'snapshots.py' and 'NormalizedAlert' not in source:
            offenders.append(f'{filename}: missing NormalizedAlert')
        if filename not in {'snapshots.py'} and 'AlertSourceStatus' not in source:
            offenders.append(f'{filename}: missing AlertSourceStatus')

    assert offenders == []


def test_compatibility_facade_is_removed_after_typed_contract_cutover() -> None:
    assert not (ALERTS / 'service.py').exists()
    assert not (ALERTS / 'queries.py').exists()

    module = _load_contracts_module()
    for contract_name in sorted(TYPED_CONTRACTS | {'AlertLoadResult'}):
        assert hasattr(module, contract_name)


def test_runtime_typed_dict_metadata_preserves_optional_provider_fields() -> None:
    module = _load_contracts_module()
    normalized_alert = module.NormalizedAlert
    source_health = module.AlertSourceHealthSummary

    assert {'route', 'value'} <= set(normalized_alert.__optional_keys__)
    assert {'route', 'value'}.isdisjoint(normalized_alert.__required_keys__)
    assert {'selected_source', 'resolved_source', 'fallback_used'} <= set(source_health.__optional_keys__)


def test_alert_characterization_is_an_explicit_release_gate() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'tests/analytics/test_alerts_characterization.py' in source


def test_runtime_dictionary_keys_match_the_typed_contracts() -> None:
    required_alert_keys, _ = _typed_dict_keys('NormalizedAlert')
    source_status_keys, _ = _typed_dict_keys('AlertSourceStatus')
    snapshot_keys, _ = _typed_dict_keys('AlertsSnapshot')
    integration_status_keys, _ = _typed_dict_keys('AlertIntegrationStatus')
    routing_keys, _ = _typed_dict_keys('AlertRoutingSummary')
    silence_keys, _ = _typed_dict_keys('AlertSilenceSummary')
    inhibition_keys, _ = _typed_dict_keys('AlertInhibitionSummary')
    ownership_keys, _ = _typed_dict_keys('AlertOwnershipSummary')
    readiness_keys, _ = _typed_dict_keys('AlertIncidentReadinessSummary')
    signal_overview_keys, _ = _typed_dict_keys('AlertSelectedClusterSignalOverview')
    signal_priority_keys, _ = _typed_dict_keys('AlertSignalPriority')
    signal_insight_keys, _ = _typed_dict_keys('AlertSignalInsight')
    signal_bars_keys, _ = _typed_dict_keys('AlertSignalBars')
    cluster_comparison_keys, _ = _typed_dict_keys('AlertClusterSignalComparisonRow')
    resource_links_keys, _ = _typed_dict_keys('AlertResourceLinks')
    resource_link_keys, resource_link_optional_keys = _typed_dict_keys('AlertResourceLink')

    alertmanager_keys = _return_dictionary_keys(SOURCES, 'normalize_alertmanager_item')
    prometheus_keys = _return_dictionary_keys(SOURCES, 'normalize_prometheus_alert')
    empty_source_keys = _return_dictionary_keys(SOURCES, 'build_empty_source_status')
    empty_snapshot_keys = _return_dictionary_keys(SNAPSHOTS, '_empty_alerts_snapshot')
    prometheus_status_keys = _return_dictionary_keys(HEALTH, 'build_prometheus_status')
    alertmanager_status_keys = _return_dictionary_keys(HEALTH, 'build_alertmanager_integration_status')
    empty_routing_keys = _return_dictionary_keys(ROUTING, 'build_empty_routing_summary')
    empty_silence_keys = _return_dictionary_keys(SILENCES, 'build_empty_silence_summary')
    inhibition_keys_runtime = _return_dictionary_keys(INHIBITION, 'build_inhibition_summary')
    empty_ownership_keys = _return_dictionary_keys(OWNERSHIP, 'build_empty_ownership_summary')
    empty_readiness_keys = _return_dictionary_keys(READINESS, 'build_empty_incident_readiness')
    empty_signal_overview_keys = _return_dictionary_keys(
        SIGNALS,
        'build_selected_cluster_signal_overview',
    )
    empty_signal_priority_keys = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_selected_cluster_signal_overview',
        'priority',
    )
    empty_signal_insight_keys = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_selected_cluster_signal_overview',
        'insight',
    )
    empty_signal_bars_keys = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_selected_cluster_signal_overview',
        'bars',
    )
    cluster_comparison_keys_runtime = _appended_dictionary_keys(
        SIGNALS,
        'build_cluster_signal_overview',
    ) | _assigned_subscript_keys(
        SIGNALS,
        'build_cluster_signal_overview',
    )
    resource_links_keys_runtime = _return_dictionary_keys(SIGNALS, 'build_resource_links')
    alertmanager_link_keys_runtime = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_resource_links',
        'alertmanager',
    )
    runbook_link_keys_runtime = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_resource_links',
        'runbook',
    )
    contact_link_keys_runtime = _nested_dictionary_keys_from_return(
        SIGNALS,
        'build_resource_links',
        'contact_point',
    )
    empty_snapshot_priority_keys = _nested_dictionary_keys_from_return(
        SNAPSHOTS,
        '_empty_alerts_snapshot',
        'priority',
    )
    empty_snapshot_insight_keys = _nested_dictionary_keys_from_return(
        SNAPSHOTS,
        '_empty_alerts_snapshot',
        'insight',
    )

    assert required_alert_keys <= alertmanager_keys
    assert required_alert_keys <= prometheus_keys
    assert source_status_keys == empty_source_keys
    assert snapshot_keys == empty_snapshot_keys
    assert integration_status_keys == prometheus_status_keys
    assert integration_status_keys == alertmanager_status_keys
    assert routing_keys == empty_routing_keys
    assert silence_keys == empty_silence_keys
    assert inhibition_keys == inhibition_keys_runtime
    assert ownership_keys == empty_ownership_keys
    assert readiness_keys == empty_readiness_keys
    assert signal_overview_keys == empty_signal_overview_keys
    assert signal_priority_keys == empty_signal_priority_keys
    assert signal_priority_keys == empty_snapshot_priority_keys
    assert signal_insight_keys == empty_signal_insight_keys
    assert signal_insight_keys == empty_snapshot_insight_keys
    assert signal_bars_keys == empty_signal_bars_keys
    assert cluster_comparison_keys == cluster_comparison_keys_runtime
    assert resource_links_keys == resource_links_keys_runtime
    assert resource_link_keys == alertmanager_link_keys_runtime
    assert resource_link_keys == runbook_link_keys_runtime
    assert resource_link_keys | resource_link_optional_keys == contact_link_keys_runtime
