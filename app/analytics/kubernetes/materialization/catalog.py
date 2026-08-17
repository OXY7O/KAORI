from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_int, require_list, require_mapping, require_str, string_tuple, unique_by

ContextBuilder = Callable[[Mapping[str, Any]], dict[str, Any]]


def _resolve_builder(path: str) -> ContextBuilder:
    module_name, separator, attribute_name = path.partition(':')
    if not separator or not module_name or not attribute_name:
        raise ValueError(f'Invalid analytics dataset builder path: {path}')
    module = import_module(module_name)
    try:
        builder = getattr(module, attribute_name)
    except AttributeError as exc:
        raise LookupError(f'Analytics dataset builder not found: {path}') from exc
    return cast(ContextBuilder, builder)


_RANGE_BUDGET_MULTIPLIER = {
    '1h': 0.5,
    '6h': 0.65,
    '12h': 0.8,
    '24h': 1.0,
    '7d': 1.25,
    '30d': 1.75,
    '60d': 2.0,
    '90d': 2.0,
}
_TREND_RANGE_BY_HOURS = {
    '1': '1h',
    '6': '6h',
    '12': '12h',
    '24': '24h',
    '168': '7d',
    '720': '30d',
    '1440': '60d',
}


@dataclass(frozen=True, slots=True)
class AnalyticsDataset:
    key: str
    label: str
    builder_path: str
    default_parameters: tuple[dict[str, str], ...]
    freshness_minutes: int
    stale_grace_minutes: int
    snapshot_parameter_keys: tuple[str, ...] = ()
    required_binding_capabilities: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    source_kind: str = 'metrics_source'
    execution_priority: int = 100
    task_budget_seconds: int = 180

    @property
    def builder(self) -> ContextBuilder:
        """Resolve the worker-only builder when a materialization run executes."""
        return _resolve_builder(self.builder_path)


def _dataset_from_definition(raw: Mapping[str, Any], path: str) -> AnalyticsDataset:
    default_parameters_raw = require_list(raw.get('default_parameters', []), f'{path}.default_parameters')
    default_parameters: list[dict[str, str]] = []
    for index, item in enumerate(default_parameters_raw):
        mapping = require_mapping(item, f'{path}.default_parameters[{index}]')
        default_parameters.append({str(key): str(value) for key, value in mapping.items()})
    source_kind = str(raw.get('source_kind') or 'metrics_source').strip()
    if source_kind not in {'metrics_source', 'alert'}:
        raise DefinitionError(f'{path}.source_kind is unsupported: {source_kind!r}.')
    return AnalyticsDataset(
        key=require_str(raw, 'key', path),
        label=require_str(raw, 'label', path),
        builder_path=require_str(raw, 'builder_path', path),
        default_parameters=tuple(default_parameters),
        freshness_minutes=require_int(raw, 'freshness_minutes', path),
        stale_grace_minutes=require_int(raw, 'stale_grace_minutes', path),
        snapshot_parameter_keys=string_tuple(raw.get('snapshot_parameter_keys'), f'{path}.snapshot_parameter_keys'),
        required_binding_capabilities=string_tuple(
            raw.get('required_binding_capabilities'),
            f'{path}.required_binding_capabilities',
        ),
        required_capabilities=string_tuple(raw.get('required_capabilities'), f'{path}.required_capabilities'),
        source_kind=source_kind,
        execution_priority=require_int(raw, 'execution_priority', path, default=100),
        task_budget_seconds=require_int(raw, 'task_budget_seconds', path, default=180),
    )


def _load_dataset_catalog() -> tuple[tuple[AnalyticsDataset, ...], AnalyticsDataset]:
    document = load_definition_document(
        'analytics/kubernetes_datasets.yaml',
        expected_kind='kubernetes_analytics_datasets',
    )
    raw_datasets = [
        require_mapping(item, f'datasets[{index}]')
        for index, item in enumerate(require_list(document.get('datasets'), 'datasets'))
    ]
    unique_by(raw_datasets, 'key', 'datasets')
    datasets = tuple(_dataset_from_definition(raw, f'datasets[{index}]') for index, raw in enumerate(raw_datasets))
    forecast_raw = require_mapping(document.get('forecast_dataset'), 'forecast_dataset')
    forecast = _dataset_from_definition(forecast_raw, 'forecast_dataset')
    if forecast.key in {item.key for item in datasets}:
        raise DefinitionError(f'Duplicate analytics dataset key: {forecast.key!r}.')
    return datasets, forecast


ANALYTICS_DATASETS, FORECAST_DATASET = _load_dataset_catalog()

_DATASET_BY_KEY = {item.key: item for item in (*ANALYTICS_DATASETS, FORECAST_DATASET)}


def get_dataset(dataset_key: str) -> AnalyticsDataset:
    try:
        return _DATASET_BY_KEY[dataset_key]
    except KeyError as exc:
        raise LookupError(f'Unknown analytics dataset: {dataset_key}') from exc


def source_binding_capabilities(dataset_key: str) -> tuple[str, ...]:
    """Return the minimum binding scope required to execute a dataset.

    Domain-specific binding capabilities remain part of Operational Domain
    Readiness, but they must not prevent a connected metrics binding from
    attempting the actual worker query. The query result is the authoritative
    runtime evidence for materialization.
    """

    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'metrics_source':
        return ('metrics',)
    return dataset.required_binding_capabilities


def source_technical_capabilities(dataset_key: str) -> tuple[str, ...]:
    """Return transport capabilities required before the worker may query.

    High-level domain capabilities such as ``workload_metrics`` and
    ``node_filesystem_identity`` are advisory readiness evidence. Instant and
    range query support are the execution boundary enforced before dispatch.
    """

    dataset = get_dataset(dataset_key)
    return tuple(
        capability for capability in dataset.required_capabilities if capability in {'instant_query', 'range_query'}
    )


def list_analytics_datasets() -> tuple[AnalyticsDataset, ...]:
    return ANALYTICS_DATASETS


def canonical_parameters(dataset_key: str, parameters: Mapping[str, Any] | None) -> dict[str, str]:
    dataset = get_dataset(dataset_key)
    source = parameters or {}
    allowed = {'cluster_id', *dataset.snapshot_parameter_keys}
    return {
        str(key): str(value)
        for key, value in sorted(source.items())
        if key in allowed and value is not None and str(value).strip() != ''
    }


def dataset_range(dataset_key: str, parameters: Mapping[str, Any] | None) -> str:
    normalized = canonical_parameters(dataset_key, parameters)
    if normalized.get('time_range'):
        return normalized['time_range']
    if normalized.get('history_window'):
        return normalized['history_window']
    return _TREND_RANGE_BY_HOURS.get(normalized.get('trend_hours', ''), '')


def dataset_task_budget_seconds(
    dataset_key: str,
    parameters: Mapping[str, Any] | None,
) -> int:
    """Estimate one dataset budget from its query horizon.

    The same estimate drives batch admission and the isolated per-dataset
    timeout, preventing a 60-day range from inheriting the same deadline as an
    instant or 24-hour query.
    """

    dataset = get_dataset(dataset_key)
    multiplier = _RANGE_BUDGET_MULTIPLIER.get(
        dataset_range(dataset_key, parameters),
        1.0,
    )
    return max(int(dataset.task_budget_seconds * multiplier), 30)
