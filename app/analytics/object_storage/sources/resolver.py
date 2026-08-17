from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.analytics.object_storage.sources.minio_metrics import MinioMetricsSourceAdapter
from app.analytics.shared.metrics import MetricsSource, MetricsSourceError, MetricsSourceFailureKind
from app.models.object_storage import ObjectStorageSystem

SourceFactory = Callable[..., MetricsSource]
SourceSupport = Callable[[ObjectStorageSystem], bool]


@dataclass(frozen=True, slots=True)
class SourceAdapterRegistration:
    """Qualified Object Storage asset profile backed by the global Metrics Source contract."""

    asset_profile: str
    supports: SourceSupport
    factory: SourceFactory


_SOURCE_ADAPTERS: tuple[SourceAdapterRegistration, ...] = (
    SourceAdapterRegistration(
        asset_profile='minio-v2',
        supports=MinioMetricsSourceAdapter.supports,
        factory=MinioMetricsSourceAdapter.for_system,
    ),
)


def resolve_object_storage_metrics_source(
    system: ObjectStorageSystem,
    *,
    execution_mode: str = 'interactive',
) -> MetricsSource:
    """Resolve the qualified asset adapter, then let MetricsConsumer resolve the source provider."""
    qualified = tuple(adapter for adapter in _SOURCE_ADAPTERS if adapter.supports(system))
    if not qualified:
        raise MetricsSourceError(
            'No qualified operational metrics adapter is registered for this Object Storage provider.',
            kind=MetricsSourceFailureKind.CONFIGURATION,
            provider='metrics_source',
        )

    diagnostics: list[MetricsSourceError] = []
    for adapter in qualified:
        try:
            return adapter.factory(system, execution_mode=execution_mode)
        except MetricsSourceError as exc:
            diagnostics.append(exc)

    first = diagnostics[0] if diagnostics else None
    if first is not None:
        raise MetricsSourceError(str(first), kind=first.kind, provider=first.provider)

    raise MetricsSourceError(
        'No supported operational metrics source is bound to this Object Storage system.',
        kind=MetricsSourceFailureKind.CONFIGURATION,
        provider='metrics_source',
    )
