from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import joinedload

from app.analytics.object_storage.sources.minio_prometheus import MinioPrometheusMetricsSource
from app.analytics.shared.metrics import MetricsSource, MetricsSourceError, MetricsSourceFailureKind
from app.models.integration import IntegrationBinding
from app.models.object_storage import ObjectStorageSystem

SourceFactory = Callable[[ObjectStorageSystem], MetricsSource]
SourceSupport = Callable[[ObjectStorageSystem], bool]


@dataclass(frozen=True, slots=True)
class SourceAdapterRegistration:
    """One qualified asset-provider + metrics-provider adapter combination."""

    metrics_provider: str
    asset_profile: str
    supports: SourceSupport
    factory: SourceFactory


_SOURCE_ADAPTERS: tuple[SourceAdapterRegistration, ...] = (
    SourceAdapterRegistration(
        metrics_provider='prometheus',
        asset_profile='minio-v2',
        supports=MinioPrometheusMetricsSource.supports,
        factory=MinioPrometheusMetricsSource.for_system,
    ),
)


def _adapters_for(provider_type: str) -> tuple[SourceAdapterRegistration, ...]:
    return tuple(adapter for adapter in _SOURCE_ADAPTERS if adapter.metrics_provider == provider_type)


def resolve_object_storage_metrics_source(system: ObjectStorageSystem) -> MetricsSource:
    """Resolve the highest-priority qualified metrics adapter for an Object Storage system."""
    bindings = (
        IntegrationBinding.query.options(joinedload(IntegrationBinding.instance))
        .filter(
            IntegrationBinding.asset_type == 'object_storage_system',
            IntegrationBinding.asset_key == str(system.id),
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .all()
    )

    supported_provider_seen = False
    diagnostics: list[MetricsSourceError] = []
    for binding in bindings:
        instance = binding.instance
        if not instance.enabled:
            continue
        provider_type = str(instance.provider_type or '').strip().lower()
        adapters = _adapters_for(provider_type)
        if not adapters:
            continue
        supported_provider_seen = True

        qualified = tuple(adapter for adapter in adapters if adapter.supports(system))
        if not qualified:
            diagnostics.append(
                MetricsSourceError(
                    f'{provider_type.title()} is bound, but no qualified metric profile is registered for this Object Storage provider.',
                    kind=MetricsSourceFailureKind.CONFIGURATION,
                    provider=provider_type,
                )
            )
            continue

        for adapter in qualified:
            try:
                return adapter.factory(system)
            except MetricsSourceError as exc:
                diagnostics.append(exc)

    if supported_provider_seen and diagnostics:
        first = diagnostics[0]
        raise MetricsSourceError(
            str(first),
            kind=first.kind,
            provider=first.provider,
        )

    raise MetricsSourceError(
        'No supported operational metrics source is bound to this Object Storage system.',
        kind=MetricsSourceFailureKind.CONFIGURATION,
    )
