from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_intelligence_workspace_copy_is_shortened_for_alerts_rules_and_control_path() -> None:
    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    rule_catalog = read('app/templates/intelligence/rule_catalog.html')
    automation_overview = read('app/templates/intelligence/partials/automation_control/_overview.html')

    assert (
        'Manage alert ownership, delivery, suppression, recovery, and resolution without duplicating '
        'channel credentials.' in alert_workspace
    )
    assert (
        'Search ownership, coverage, readiness, severity, and response. View Rule expands below the selected record.'
        in rule_catalog
    )
    assert (
        'Evidence moves through runbook matching, review, execution admission, and verification. Later gates cannot '
        'bypass earlier controls.' in automation_overview
    )


def test_system_runbook_detail_uses_enhanced_icon_cards_and_wider_guidance_row() -> None:
    template = read('app/templates/intelligence/partials/automation_control/_runbooks.html')

    assert 'data-automation-runbook-detail="enhanced"' in template
    assert 'data-automation-runbook-evidence-grid="summary"' in template
    assert 'data-automation-runbook-guidance-grid="verification-recovery"' in template
    assert 'data-automation-runbook-controls="enhanced"' in template
    for icon in (
        'rotate-cw',
        'files',
        'shield-check',
        'clipboard-check',
        'life-buoy',
        'sliders-horizontal',
        'fingerprint',
    ):
        assert f'data-lucide="{icon}"' in template
    assert 'lg:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.75fr)]' in template
    assert 'inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-kaori-primary' in template
