from collections.abc import Callable

from app.platform_operations.data_lifecycle.retention.domains.analytics_snapshot import AnalyticsSnapshotArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.generated_report import GeneratedReportArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.job_execution import JobExecutionArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.operational_activity import (
    OperationalActivityArchiveDomain,
)
from app.platform_operations.data_lifecycle.retention.domains.runtime_observation import RuntimeObservationArchiveDomain
from app.platform_operations.data_lifecycle.retention.types import ArchiveDomain

DOMAIN_FACTORIES: dict[str, Callable[[], ArchiveDomain]] = {
    'analytics_snapshot': AnalyticsSnapshotArchiveDomain,
    'generated_report': GeneratedReportArchiveDomain,
    'operational_activity': OperationalActivityArchiveDomain,
    'job_execution': JobExecutionArchiveDomain,
    'runtime_observation': RuntimeObservationArchiveDomain,
}


def get_archive_domain(domain_name: str) -> ArchiveDomain:
    normalized = domain_name.strip().lower().replace('-', '_')
    factory = DOMAIN_FACTORIES.get(normalized)
    if factory is None:
        supported = ', '.join(sorted(DOMAIN_FACTORIES))
        raise ValueError(f'Unsupported archive domain: {domain_name}. Supported domains: {supported}.')
    return factory()


__all__ = [
    'DOMAIN_FACTORIES',
    'AnalyticsSnapshotArchiveDomain',
    'GeneratedReportArchiveDomain',
    'OperationalActivityArchiveDomain',
    'JobExecutionArchiveDomain',
    'RuntimeObservationArchiveDomain',
    'get_archive_domain',
]
