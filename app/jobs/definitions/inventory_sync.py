from app.jobs.definitions.base import JobDefinition

JOB_KEY = 'kubernetes.inventory.sync'
ADAPTER_MODULE = 'app.inventory.job_adapter'

INVENTORY_SYNC_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name='Inventory Sync',
    domain='Kubernetes Inventory',
    description='Refresh Kubernetes inventory across eligible clusters.',
    icon='database-zap',
    queue_name='inventory',
    workload_class='standard',
    job_type='kubernetes_inventory',
    operation='inventory_sync_all',
    scope_type='kubernetes_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='clusters.sync',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_inventory_sync',
    context_builder_path=f'{ADAPTER_MODULE}:build_inventory_sync_context',
    configuration_template='jobs/configuration/definitions/inventory_sync.html',
    default_enabled=True,
    default_interval_minutes=60,
    safety_summary='Each cluster promotes inventory only after a complete generation commits successfully.',
    execution_summary='Run a fleet inventory refresh and monitor the canonical execution without leaving this page.',
    recent_execution_summary='Latest scheduled and manual fleet inventory synchronizations.',
)
