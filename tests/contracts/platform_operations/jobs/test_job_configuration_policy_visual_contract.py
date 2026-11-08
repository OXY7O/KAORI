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
