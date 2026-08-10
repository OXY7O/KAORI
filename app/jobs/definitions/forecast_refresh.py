from app.common.job_execution_contract import registered_job_operation_label
from app.jobs.definitions.base import JobDefinition

ADAPTER_MODULE = 'app.analytics.job_adapter'

JOB_KEY = 'analytics.forecast.materialize'

FORECAST_REFRESH_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name=registered_job_operation_label('materialize_forecast'),
    domain='Kubernetes Analytics',
    description='Generate persistent capacity forecasts on the forecasting worker.',
    icon='chart-spline',
    queue_name='forecasting',
    workload_class='forecasting',
    job_type='forecast_materialization',
    operation='materialize_forecast',
    scope_type='forecast_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='analytics.view',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_forecast_materialization',
    context_builder_path=f'{ADAPTER_MODULE}:build_forecast_materialization_context',
    configuration_template='jobs/configuration/definitions/forecast_refresh.html',
    default_enabled=True,
    default_interval_minutes=120,
    minimum_interval_minutes=30,
    maximum_interval_minutes=1440,
    safety_summary=(
        'Forecast range queries run in the forecasting queue and the last successful result '
        'remains available during refresh.'
    ),
    execution_summary='Generate reusable forecast history snapshots and monitor the forecasting worker.',
    recent_execution_summary='Latest forecast history materialization runs.',
    default_configuration={
        'history_windows': ['7d', '30d', '90d'],
        'freshness_minutes': 120,
        'stale_grace_minutes': 4320,
    },
)
