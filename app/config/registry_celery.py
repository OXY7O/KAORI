from __future__ import annotations

REGISTRY_CELERY_IMPORTS = (
    'app.artifact_registry.tasks',
    'app.artifact_registry.security.tasks',
    'app.artifact_registry.governance_tasks',
    'app.artifact_registry.correlation_tasks',
)


def registry_task_routes(security_queue: str) -> dict[str, dict[str, str]]:
    """Return canonical Artifact Registry worker routing."""
    return {
        'app.artifact_registry.tasks.sync_all_registry': {'queue': 'inventory'},
        'app.artifact_registry.security.tasks.sync_all_registry_security': {'queue': security_queue},
        'app.artifact_registry.security.tasks.sync_registry_security_source': {'queue': security_queue},
        'app.artifact_registry.security.tasks.finalize_registry_security_sync': {'queue': security_queue},
        'app.artifact_registry.governance_tasks.sync_all_registry_governance': {'queue': 'inventory'},
        'app.artifact_registry.correlation_tasks.materialize_registry_runtime_correlation': {'queue': 'inventory'},
    }
