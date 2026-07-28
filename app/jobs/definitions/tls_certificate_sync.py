from app.jobs.definitions.base import JobDefinition

JOB_KEY = 'governance.tls_certificates.sync'
ADAPTER_MODULE = 'app.governance.tls_certificates.job_adapter'

TLS_CERTIFICATE_SYNC_DEFINITION = JobDefinition(
    key=JOB_KEY,
    name='TLS Certificate Sync',
    domain='Kubernetes Governance',
    description='Refresh TLS Secret inventory, Ingress usage, expiry, and freshness.',
    icon='shield-check',
    queue_name='inventory',
    workload_class='standard',
    job_type='tls_certificate_inventory',
    operation='tls_certificate_sync',
    scope_type='kubernetes_fleet',
    scope_key='all',
    configure_permission='jobs.configure',
    execute_permission='jobs.execute',
    domain_execute_permission='tls_certificates.sync',
    dispatcher_path=f'{ADAPTER_MODULE}:dispatch_tls_certificate_sync',
    context_builder_path=f'{ADAPTER_MODULE}:build_tls_certificate_sync_context',
    configuration_template='jobs/configuration/definitions/tls_certificate_sync.html',
    default_enabled=True,
    default_interval_minutes=360,
    minimum_interval_minutes=30,
    maximum_interval_minutes=1440,
    safety_summary=(
        'Each cluster is collected independently and replaces only its committed TLS inventory '
        'after the Kubernetes API read completes.'
    ),
    execution_summary='Refresh TLS Secret inventory across eligible clusters and monitor the active worker run.',
    recent_execution_summary='Latest scheduled and manual TLS Secret inventory refreshes.',
)
