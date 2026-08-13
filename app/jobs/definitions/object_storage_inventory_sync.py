from app.common.job_execution_contract import (
    OBJECT_STORAGE_INVENTORY_SYNC_OPERATION,
    registered_job_operation_label,
)
from app.jobs.definitions.base import JobDefinition

JOB_KEY = 'object_storage.inventory.sync'
ADAPTER_MODULE = 'app.storage_inventory.job_adapter'

OBJECT_STORAGE_INVENTORY_SYNC_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name=registered_job_operation_label(OBJECT_STORAGE_INVENTORY_SYNC_OPERATION),
    domain='Object Storage Inventory',
    description='Refresh committed bucket inventory across eligible managed object-storage systems.',
    icon='database-zap',
    queue_name='inventory',
    workload_class='standard',
    job_type='object_storage_inventory',
    operation=OBJECT_STORAGE_INVENTORY_SYNC_OPERATION,
    scope_type='object_storage_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='storage.sync',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_object_storage_inventory_sync',
    context_builder_path=f'{ADAPTER_MODULE}:build_object_storage_inventory_sync_context',
    configuration_template='jobs/configuration/definitions/object_storage_inventory_sync.html',
    default_enabled=True,
    default_interval_minutes=60,
    safety_summary='Each system replaces its committed bucket snapshot only after collection succeeds.',
    execution_summary='Run an object-storage inventory refresh and monitor the canonical execution without leaving this page.',
    recent_execution_summary='Latest scheduled and manual object-storage inventory synchronizations.',
)
