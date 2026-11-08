from collections.abc import Callable

from app.platform_operations.data_lifecycle.retention.domains.alert_incident import AlertIncidentArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.analytics_snapshot import AnalyticsSnapshotArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.audit_event import AuditEventArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.generated_report import GeneratedReportArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.job_execution import JobExecutionArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.notification_delivery import (
    NotificationDeliveryArchiveDomain,
)
from app.platform_operations.data_lifecycle.retention.domains.operational_activity import (
    OperationalActivityArchiveDomain,
)
from app.platform_operations.data_lifecycle.retention.domains.runtime_observation import RuntimeObservationArchiveDomain
from app.platform_operations.data_lifecycle.retention.domains.tenant_audit_evidence import (
    TenantAuditEvidenceArchiveDomain,
)
from app.platform_operations.data_lifecycle.retention.types import ArchiveDomain

DOMAIN_FACTORIES: dict[str, Callable[[], ArchiveDomain]] = {
    'alert_incident': AlertIncidentArchiveDomain,
    'audit_event': AuditEventArchiveDomain,
    'analytics_snapshot': AnalyticsSnapshotArchiveDomain,
    'generated_report': GeneratedReportArchiveDomain,
    'operational_activity': OperationalActivityArchiveDomain,
    'job_execution': JobExecutionArchiveDomain,
    'notification_delivery': NotificationDeliveryArchiveDomain,
    'runtime_observation': RuntimeObservationArchiveDomain,
    'tenant_audit_evidence': TenantAuditEvidenceArchiveDomain,
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
    'AlertIncidentArchiveDomain',
    'AuditEventArchiveDomain',
    'AnalyticsSnapshotArchiveDomain',
    'GeneratedReportArchiveDomain',
    'OperationalActivityArchiveDomain',
    'JobExecutionArchiveDomain',
    'NotificationDeliveryArchiveDomain',
    'RuntimeObservationArchiveDomain',
    'TenantAuditEvidenceArchiveDomain',
    'get_archive_domain',
]
