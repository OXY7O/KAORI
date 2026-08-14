from app.common.job_execution_contract import (
    OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
    registered_job_operation_label,
)
from app.jobs.definitions.base import JobDefinition

ADAPTER_MODULE = 'app.analytics.object_storage.job_adapter'
JOB_KEY = 'object_storage.forecast.materialize'

OBJECT_STORAGE_FORECAST_REFRESH_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name=registered_job_operation_label(OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION),
    domain='Object Storage Analytics',
    description='Generate persistent Object Storage capacity forecasts on the forecasting worker.',
    icon='chart-spline',
    queue_name='forecasting',
    workload_class='forecasting',
    job_type='object_storage_forecast_materialization',
    operation=OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
    scope_type='object_storage_forecast_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='analytics.view',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_object_storage_forecast_materialization',
    context_builder_path=f'{ADAPTER_MODULE}:build_object_storage_forecast_materialization_context',
    configuration_template='jobs/configuration/definitions/forecast_refresh.html',
    default_enabled=True,
    default_interval_minutes=120,
    minimum_interval_minutes=30,
    maximum_interval_minutes=1440,
    safety_summary=(
        'Forecast range queries run on the forecasting queue. The last usable committed result remains available '
        'when a refresh fails inside its stale-grace window.'
    ),
    execution_summary='Generate reusable Object Storage forecast snapshots and monitor the forecasting worker.',
    recent_execution_summary='Latest Object Storage forecast materialization runs.',
    default_configuration={
        'history_windows': ['7d', '30d', '90d'],
        'freshness_minutes': 120,
        'stale_grace_minutes': 4320,
    },
)
