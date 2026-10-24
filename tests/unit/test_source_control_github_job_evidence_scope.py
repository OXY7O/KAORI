"""Source Control UAT must not misattribute other JobExecutions to GitHub."""

from __future__ import annotations

from sqlalchemy import create_engine, select, text

from app.integrations.source_control.source_control.providers.github.application.uat_routes import (
    _installation_job_predicate,
)
from app.models.job import JobExecution


def test_recent_jobs_requires_source_control_type_operation_and_exact_scope() -> None:
    # An isolated SQL table is sufficient to execute the production predicate;
    # no provider connection, scheduler, Celery task or full schema is needed.
    engine = create_engine('sqlite+pysqlite:///:memory:')
    rows = [
        (1, 'source_control', 'integration_operation', 'full_validation', 42, 'integration_instance', None),
        (2, 'source_control', 'integration_operation', 'runtime_refresh', 42, 'integration_instance', None),
        (3, 'source_control', 'source_control_repository_inventory', 'sync_source_control_repositories',
         None, 'source_control_installation', 'installation:7'),
        (4, 'registry', 'source_control_repository_inventory', 'sync_source_control_repositories',
         None, 'source_control_installation', 'installation:7'),
        (5, 'source_control', 'unrelated_job', 'sync_source_control_repositories',
         None, 'source_control_installation', 'installation:7'),
        (6, 'source_control', 'source_control_repository_inventory', 'unrelated_operation',
         None, 'source_control_installation', 'installation:7'),
        (7, 'source_control', 'source_control_repository_inventory', 'sync_source_control_repositories',
         None, 'source_control_installation', 'installation:8'),
        (8, 'source_control', 'source_control_repository_inventory', 'sync_source_control_repositories',
         None, 'integration_instance', 'installation:7'),
        (9, 'source_control', 'integration_operation', 'unrelated_operation',
         42, 'integration_instance', None),
        (10, 'source_control', 'integration_operation', 'full_validation',
         43, 'integration_instance', None),
        (11, 'source_control', 'integration_operation', 'full_validation',
         42, 'source_control_installation', None),
        (12, None, 'source_control_repository_inventory', 'sync_source_control_repositories',
         None, 'source_control_installation', 'installation:7'),
    ]
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                'CREATE TABLE job_executions ('
                'id INTEGER PRIMARY KEY, integration_type TEXT, job_type TEXT, '
                'operation TEXT, integration_instance_id INTEGER, '
                'scope_type TEXT, scope_key TEXT)'
            )
            connection.execute(
                text('INSERT INTO job_executions '
                     '(id, integration_type, job_type, operation, integration_instance_id, '
                     'scope_type, scope_key) VALUES '
                     '(:id, :integration_type, :job_type, :operation, '
                     ':integration_instance_id, :scope_type, :scope_key)'),
                [
                    dict(zip(
                        ('id', 'integration_type', 'job_type', 'operation',
                         'integration_instance_id', 'scope_type', 'scope_key'),
                        row, strict=True,
                    ))
                    for row in rows
                ],
            )
            result = connection.execute(
                select(JobExecution.__table__.c.id)
                .where(_installation_job_predicate(integration_instance_id=42, installation_id=7))
                .order_by(JobExecution.__table__.c.id)
            ).scalars().all()
            assert result == [1, 2, 3]
    finally:
        engine.dispose()
