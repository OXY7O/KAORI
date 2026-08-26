from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operation_center_overview_copy_is_compact() -> None:
    source = read('app/platform_operations/overview/presentation.py')

    for required in (
        'Canonical execution and worker evidence.',
        'Retention, verified archives, and safe cleanup.',
        'Protected Kubernetes controls with readiness and authorization gates.',
    ):
        assert required in source

    for retired in (
        'Canonical execution, retry, cancellation, queue, and worker evidence.',
        'Retention policy, verified archive evidence, and safe cleanup boundaries.',
        'Protected Kubernetes controls with explicit readiness and authorization boundaries.',
    ):
        assert retired not in source


def test_object_storage_job_catalog_copy_is_compact() -> None:
    source = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')

    for required in (
        'Refresh committed bucket inventory for eligible object storage systems.',
        'Refresh Object Storage analytics snapshots.',
        'Generate Object Storage capacity forecasts.',
    ):
        assert required in source

    for retired in (
        'Refresh committed bucket inventory across eligible managed object-storage systems.',
        'Refresh shared Object Storage operational analytics snapshots on the analytics worker.',
        'Generate persistent Object Storage capacity forecasts on the forecasting worker.',
    ):
        assert retired not in source


def test_data_lifecycle_workspace_guidance_is_compact() -> None:
    domain = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    storage = read('app/templates/platform_operations/data_lifecycle/partials/_storage.html')

    for required in (
        'Hot storage stays domain-owned; verified archives use the shared Data Lifecycle target.',
        'Retention changes eligibility only; no job runs immediately.',
        'Cleanup stays blocked; transient failures retry once, then require manual retry.',
    ):
        assert required in domain

    assert 'Cleanup stays blocked; transient failures retry once, then require manual retry.' in storage

    for retired in (
        'Hot source storage remains domain-owned; verified cold archives use the shared Data Lifecycle archive target.',
        'Changing retention days only changes eligibility; it does not run a job immediately.',
        'Cleanup stays blocked. Transient failures retry once; exhausted failures require manual retry.',
    ):
        assert retired not in domain
    assert 'Cleanup stays blocked. Transient failures retry once; exhausted failures require manual retry.' not in storage


def test_data_lifecycle_evidence_copy_is_compact() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    reports = read('app/platform_operations/data_lifecycle/retention/generated_report_presentation.py')

    for required in (
        'Case lifecycle evidence from detection through closure.',
        'Provider-neutral across Kubernetes, Object Storage, Metrics Source, Alertmanager, and future runtime integrations.',
    ):
        assert required in presentation

    assert 'Ready reports use hot retention; Failed and Archived use dedicated windows.' in reports
    assert 'Artifacts archive before cleanup.' in reports

    assert (
        'Detection, acknowledgement, assignment, silence, remediation, source resolution, and closure evidence.'
        not in presentation
    )
    assert (
        'The policy is provider-neutral. Kubernetes, Object Storage, Metrics Source, Alertmanager, and future integrations '
        'using IntegrationRuntimeObservation share the same lifecycle boundary.'
        not in presentation
    )
