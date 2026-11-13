"""Presentation-only policy Guide and compact evidence UAT contract (#4606)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_and_generated_report_policies_reuse_title_level_guides() -> None:
    template = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    component = read('app/templates/components/info_tip.html')

    Environment().parse(template)
    assert template.count("variant='guide'") == 4
    assert "selected.name == 'analytics_snapshot'" in template
    assert "selected.name == 'generated_report'" in template
    assert "info_tip.render('data-lifecycle-analytics-snapshots-policy-guide'" in template
    assert "info_tip.render('data-lifecycle-generated-reports-policy-guide'" in template
    assert 'top consumers' in template
    assert 'stale-serve grace and hot-retention boundaries' in template
    assert 'Ready, Failed and Archived reports use status-specific hot-retention windows.' in template
    assert 'checksum-verified before cleanup' in template
    assert 'Requested, Queued, Generating, active regeneration jobs' in template
    assert "placement='right'" in template
    assert 'data-kaori-info-tip-variant=' in component
    assert 'data-kaori-info-tip-trigger' in component
    assert "selected.name == 'audit_event'" in template
    assert "selected.name == 'alert_incident'" in template


def test_automatic_run_keeps_source_derived_schedule_and_two_short_lines() -> None:
    template = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    schedule = read('app/platform_operations/data_lifecycle/retention/presentation.py')

    assert '<span class="block">Policy + schedule required.</span>' in template
    assert "<span class=\"block\">{{ lifecycle.next_schedule_label or 'No scheduled run.' }}</span>" in template
    assert 'Requires Policy enabled + Scheduled execution.' not in template
    assert "selected.name in ('notification_delivery', 'audit_event')" in template
    assert "candidate.strftime('%d %b %Y %H:%M %Z')" in schedule
    assert "The dispatcher checks due policies every 15 minutes." in template
    assert 'whitespace-nowrap' not in template


def test_analytics_and_generated_coverage_copy_keeps_source_ownership() -> None:
    template = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    coverage = read('app/platform_operations/data_lifecycle/retention/domain_coverage.py')
    generated = read('app/platform_operations/data_lifecycle/retention/generated_report_presentation.py')

    assert '{% for item in lifecycle.coverage %}' in template
    assert '{{ item.description }}' in template
    assert 'Capacity, utilization, storage, workload and alert data.' in coverage
    assert 'Forecast snapshots in shared analytics storage.' in coverage
    assert 'Ready, Failed and Archived after hot retention.' in generated
    assert 'PDF/XLSX/CSV checksum-verified before cleanup.' in generated
    assert 'Source files stay intact until archive and supplements pass verification.' in generated
    assert "GENERATED_REPORT_COVERAGE_NOTE = (" in generated


def test_audit_exclusion_and_generated_exclusion_are_compact_but_protected() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    generated = read('app/platform_operations/data_lifecycle/retention/generated_report_presentation.py')
    template = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    audit = read('app/platform_operations/data_lifecycle/retention/domains/audit_event.py')

    assert 'Raw metadata, IP/UA, actor reconstruction, bundle downloads, schedules, cleanup and record lookup ' in (
        presentation
    )
    assert "'are excluded.'" in presentation
    assert 'Pending or unsafe-artifact reports are protected.' in generated
    assert 'Generated Reports Policy' in template
    assert 'Request' in template and 'safe artifact references remain protected.' in template
    assert "GENERATED_REPORT_EXCLUSION_NOTE" in presentation
    assert 'cleanup_supported = False' in audit
    assert 'retention and access restricted.' in presentation
