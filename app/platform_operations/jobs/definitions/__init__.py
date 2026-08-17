from app.platform_operations.jobs.definition_types import JobDefinition, RegisteredJobDispatchResult
from app.platform_operations.jobs.registry import get_job_definition

INVENTORY_SYNC_DEFINITION = get_job_definition('kubernetes.inventory.sync')
OBJECT_STORAGE_INVENTORY_SYNC_DEFINITION = get_job_definition('object_storage.inventory.sync')
OBJECT_STORAGE_FORECAST_REFRESH_DEFINITION = get_job_definition('object_storage.forecast.materialize')
REPORT_SCHEDULE_DEFINITION = get_job_definition('reports.schedule.dispatch')
TLS_CERTIFICATE_SYNC_DEFINITION = get_job_definition('governance.tls_certificates.sync')
ANALYTICS_REFRESH_DEFINITION = get_job_definition('analytics.materialize')
FORECAST_REFRESH_DEFINITION = get_job_definition('analytics.forecast.materialize')

__all__ = [
    'ANALYTICS_REFRESH_DEFINITION',
    'FORECAST_REFRESH_DEFINITION',
    'INVENTORY_SYNC_DEFINITION',
    'OBJECT_STORAGE_INVENTORY_SYNC_DEFINITION',
    'OBJECT_STORAGE_FORECAST_REFRESH_DEFINITION',
    'REPORT_SCHEDULE_DEFINITION',
    'TLS_CERTIFICATE_SYNC_DEFINITION',
    'JobDefinition',
    'RegisteredJobDispatchResult',
]
