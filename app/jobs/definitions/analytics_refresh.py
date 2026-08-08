from app.jobs.definitions.base import JobDefinition

ADAPTER_MODULE = 'app.analytics.job_adapter'

JOB_KEY = 'analytics.materialize'

ANALYTICS_REFRESH_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name='Analytics Data Refresh',
    domain='Kubernetes Analytics',
    description='Refresh shared Kubernetes analytics snapshots.',
    icon='chart-no-axes-combined',
    queue_name='analytics-batch',
    workload_class='analytics',
    job_type='analytics_materialization',
    operation='materialize_analytics',
    scope_type='analytics_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='analytics.view',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_analytics_materialization',
    context_builder_path=f'{ADAPTER_MODULE}:build_analytics_materialization_context',
    configuration_template='jobs/configuration/definitions/analytics_refresh.html',
    default_enabled=True,
    default_interval_minutes=15,
    minimum_interval_minutes=5,
    maximum_interval_minutes=1440,
    safety_summary='Long-range results are generated once per cluster and parameter set, then shared by every user.',
    execution_summary='Materialize shared analytics snapshots and monitor worker progress from one execution workspace.',
    recent_execution_summary='Latest shared analytics snapshot materialization runs.',
    default_configuration={
        'time_ranges': ['24h', '7d', '30d', '60d'],
        'freshness_minutes': 15,
        'stale_grace_minutes': 1440,
    },
)
