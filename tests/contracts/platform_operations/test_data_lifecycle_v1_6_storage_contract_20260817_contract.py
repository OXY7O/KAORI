from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_policy_workspace_explains_hot_and_archive_storage_ownership() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    storage_presentation = read('app/platform_operations/data_lifecycle/retention/storage_presentation.py')
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert 'def build_storage_contract_context(' in storage_presentation
    contract_body = storage_presentation.split('def build_storage_contract_context(', 1)[1].split(
        'def artifact_matches_storage_profile(', 1
    )[0]
    assert '_probe_storage_endpoint' not in contract_body
    assert "selected_context['storage_contract'] = _build_selected_storage_contract(selected)" in presentation
    assert "elif name == 'runtime_observation':" in presentation
    assert 'no integration-specific archive bucket is created' in presentation

    for token in (
        'Storage Boundary',
        'Hot Source',
        'Verified Archive',
        'Payload:',
        'Shared Archive Control Plane',
        'Open Archive Storage',
    ):
        assert token in workspace


def test_runtime_observation_storage_contract_is_shared_and_provider_neutral() -> None:
    runtime_domain = read('app/platform_operations/data_lifecycle/retention/domains/runtime_observation.py')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    readme = read('app/platform_operations/data_lifecycle/retention/README.md')

    assert "source_model = 'integration_runtime_observations'" in runtime_domain
    assert "source_label = 'PostgreSQL'" in presentation
    assert "archive_content = 'JSONL.GZ data + manifest JSON'" in presentation
    assert 'shared archive target' in presentation
    assert 'do not configure independent archive buckets' in readme
    assert 'do not carry supplemental binary artifacts' in readme


def test_lifecycle_migration_chain_restores_schedule_evidence_revision() -> None:
    schedule_migration = read('migrations/versions/20260816_schedule_run_evidence.py')
    lifecycle_seed = read('migrations/versions/20260817_lifecycle_policy_seed.py')

    assert "revision = '20260816_schedule_run_evidence'" in schedule_migration
    assert "down_revision = '20260816_report_lifecycle'" in schedule_migration
    assert "down_revision = '20260816_schedule_run_evidence'" in lifecycle_seed
    assert "sa.inspect(bind).get_columns('report_schedule_runs')" in schedule_migration
    assert 'if not _has_schedule_snapshot(bind):' in schedule_migration
    assert 'if _has_schedule_snapshot(bind):' in schedule_migration


def test_runtime_observation_lifecycle_includes_object_storage_runtime_history() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    runtime_domain = read('app/platform_operations/data_lifecycle/retention/domains/runtime_observation.py')
    minio_adapter = read('app/integrations/storage/object_storage/providers/minio/adapter.py')
    validation_tasks = read('app/integrations/validation/tasks.py')
    readme = read('app/platform_operations/data_lifecycle/retention/README.md')
    runtime_history = read('app/templates/integrations/partials/_runtime_history.html')

    assert "'label': 'Object Storage · MinIO'" in presentation
    assert 'MinIO Object Storage integration targets' in presentation
    assert "source_model = 'integration_runtime_observations'" in runtime_domain
    assert 'IntegrationRuntimeObservation.provider ==' not in runtime_domain
    assert '.filter_by(provider=' not in runtime_domain
    assert 'return RuntimeState(' in minio_adapter
    assert 'persist_runtime_state(' in validation_tasks
    assert 'MinIO Object Storage' in readme
    assert 'History follows the shared Data Lifecycle policy.' in runtime_history


def test_storage_boundary_is_a_compact_hot_to_archive_path() -> None:
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert 'grid gap-3 px-4 py-3.5 lg:grid-cols-[minmax(0,1fr)_2rem_minmax(0,1fr)]' in workspace
    assert 'Verified Archive' in workspace
    assert 'Payload:' in workspace
    assert 'Ownership:' in workspace
    storage_section = workspace.split('data-lifecycle-storage-boundary-title', 2)[-1].split('</section>', 1)[0]
    assert 'xl:grid-cols-4' not in storage_section
    assert 'rounded-lg border border-outline-default bg-surface-subtle' not in storage_section
