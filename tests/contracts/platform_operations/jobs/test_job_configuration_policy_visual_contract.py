from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFINITIONS = ROOT / 'app' / 'templates' / 'platform_operations' / 'jobs' / 'configuration' / 'definitions'


def _read(name: str) -> str:
    return (DEFINITIONS / name).read_text(encoding='utf-8')


def test_all_policy_workspaces_use_visual_policy_shell():
    shared = (DEFINITIONS.parent / '_schedule_policy.html').read_text(encoding='utf-8')
    assert 'macro header(' in shared
    assert 'macro footer(' in shared
    for label in ('Policy &amp; Configuration', 'bg-kaori-soft', 'Schedule Status', 'Save Policy'):
        assert label in shared

    for name in ('inventory_sync.html', 'tls_certificate_sync.html', '_materialization_job.html'):
        source = _read(name)
        assert 'components/operational_section_card.html' in source
        assert 'operational_section.shell_classes()' in source
        assert 'platform_operations/jobs/configuration/_schedule_policy.html' in source
        assert 'schedule_policy.header(' in source
        assert 'schedule_policy.footer(' in source
        assert 'Policy Timeline' in source
        assert 'policy_form.hidden_tag()' in source


def test_policy_layout_does_not_restore_small_card_wall():
    for name in ('inventory_sync.html', 'tls_certificate_sync.html', '_materialization_job.html'):
        source = _read(name)
        assert 'sm:grid-cols-3 lg:col-span-12' not in source
        assert source.count('rounded-lg border border-outline-subtle bg-surface-hover p-3') == 0


def test_materialization_ranges_are_compact_and_not_nested_fieldsets():
    analytics = _read('analytics_refresh.html')
    forecast = _read('forecast_refresh.html')
    assert '<fieldset' not in analytics
    assert '<fieldset' not in forecast
    assert 'Precomputed Time Ranges' in analytics
    assert 'Precomputed History Windows' in forecast
    assert 'sm:grid-cols-2 lg:grid-cols-4' in analytics
    assert 'sm:grid-cols-3' in forecast


def test_registered_job_configuration_headers_use_neutral_shared_surfaces() -> None:
    overview = (DEFINITIONS.parent / '_job_overview.html').read_text(encoding='utf-8')
    policy = (DEFINITIONS.parent / '_schedule_policy.html').read_text(encoding='utf-8')
    catalog = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text(
        encoding='utf-8'
    )

    neutral_header = 'header class="border-b border-outline-subtle bg-surface-card px-5 py-4 sm:px-6"'
    assert overview.count(neutral_header) == 1
    assert policy.count(neutral_header) == 2  # Scheduled and Manual Only.
    assert 'border-b border-outline-subtle bg-surface-hover px-5 py-4' not in overview
    assert 'border-b border-kaori-primary/15 bg-kaori-soft px-5 py-4' not in policy
    assert policy.count('rounded-lg bg-kaori-soft text-kaori-primary shadow-sm') == 2
    assert 'status_indicator_label(' in policy
    assert 'policy_form.enabled(' in policy
    assert 'policy_form.interval_minutes(' in policy

    templates = {
        line.split(':', 1)[1].strip()
        for line in catalog.splitlines()
        if line.strip().startswith('configuration_template:')
    }
    assert len(templates) >= 15

    for template_path in templates:
        assert template_path.startswith('platform_operations/jobs/configuration/definitions/')
        source = (ROOT / 'app/templates' / template_path).read_text(encoding='utf-8')
        if '_materialization_job.html' in source:
            # Analytics and forecast jobs inherit the shared overview and policy.
            materialization = (DEFINITIONS / '_materialization_job.html').read_text(encoding='utf-8')
            assert '_job_overview.html' in materialization
            assert 'schedule_policy.header(' in materialization
        else:
            assert '_job_overview.html' in source, template_path

    for filename in ('object_storage_inventory_sync.html', 'artifact_registry_inventory_sync.html'):
        source = _read(filename)
        assert neutral_header in source
        assert 'border-b border-kaori-primary/15 bg-kaori-soft' not in source
        assert 'bg-status-warning-soft text-status-warning-text shadow-sm' in source
        assert 'Guarded Recovery Boundary' in source
        assert 'manual_form.hidden_tag()' in source
        assert 'confirmation_phrase' in source

    # Preserve the different colored functional controls and state on white headers.
    assert 'border border-kaori-primary/20 bg-kaori-soft' in policy
    assert 'peer-checked:bg-kaori-primary' in policy
    assert 'text-status-warning-text' in _read('object_storage_inventory_sync.html')
