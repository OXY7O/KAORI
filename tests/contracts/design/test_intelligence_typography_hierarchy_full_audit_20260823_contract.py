import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INTELLIGENCE_TEMPLATES = ROOT / 'app/templates/intelligence'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_intelligence_heading_line_height_matches_size_hierarchy() -> None:
    violations: list[str] = []
    for template in sorted(INTELLIGENCE_TEMPLATES.rglob('*.html')):
        source = template.read_text(encoding='utf-8')
        for line_number, line in enumerate(source.splitlines(), start=1):
            match = re.search(r'<h[1-5]\b[^>]*class="([^"]*)"', line)
            if match is None:
                continue
            classes = match.group(1)
            if 'text-sm' in classes and 'font-semibold' in classes and 'leading-5' not in classes:
                violations.append(f'{template.relative_to(ROOT)}:{line_number}: text-sm heading missing leading-5')
            if 'text-base' in classes and 'font-semibold' in classes and 'leading-6' not in classes:
                violations.append(f'{template.relative_to(ROOT)}:{line_number}: text-base heading missing leading-6')
            if 'text-lg' in classes and 'font-semibold' in classes and 'leading-7' not in classes:
                violations.append(f'{template.relative_to(ROOT)}:{line_number}: text-lg heading missing leading-7')
    assert not violations, '\n'.join(violations)


def test_intelligence_primary_section_components_use_canonical_description_scale() -> None:
    workspace = read('app/templates/intelligence/components/_workspace.html')
    automation_components = read('app/templates/intelligence/partials/automation_control/_components.html')

    assert 'text-base font-semibold leading-6 text-content-primary' in workspace
    assert 'max-w-4xl text-sm leading-6 text-content-secondary' in workspace
    assert 'text-base font-semibold leading-6 text-content-primary' in automation_components
    assert 'max-w-4xl text-sm leading-6 text-content-secondary' in automation_components
    assert 'max-w-4xl text-xs leading-5 text-content-muted' not in automation_components


def test_each_intelligence_page_uses_primary_section_hierarchy() -> None:
    overview = read('app/templates/intelligence/overview.html')
    recommendations = read('app/templates/intelligence/recommendations.html')
    recommendation_summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    alert_page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    rule_catalog = read('app/templates/intelligence/rule_catalog.html')
    rule_summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    automation = read('app/templates/intelligence/automation_control.html')

    assert "'Intelligence Posture'" in overview
    assert "'Intelligence Workspaces'" in overview

    assert "'Recommendation Summary'" in recommendation_summary
    assert "'Recommendation Workspace'" in recommendations

    assert 'Alert Intelligence' in alert_page
    assert "'Alert Operations Summary'" in alert_summary
    assert "'Alert Operations Workspace'" in alert_workspace

    assert "'Rule Catalog Summary'" in rule_summary
    assert "'Rule Definitions'" in rule_catalog
    assert 'intelligence_ui.posture_panel(' in rule_summary

    assert "'Automation Control Summary'" in automation
    assert '<h2 class="{{ table_ui.block_title_classes() }}">Automation Control Workspace</h2>' in automation


def test_recommendation_modal_primary_sections_keep_description_hierarchy() -> None:
    modal = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    primary_descriptions = (
        'Read the matched condition and operational consequence before changing the live resource.',
        'Resource identity stays separate from measurements so the operator can confirm exactly what will be investigated.',
        'Thresholds, observed values, and snapshot basis are presented as an audit ledger rather than repeated cards.',
        'Alert Intelligence owns acknowledgement, silences, channel delivery, recovery verification, and history after promotion.',
        'A single connected sequence keeps the operator focused on the next decision, not on separate cards.',
        'Canonical source, evaluator, domain, and rule identity used to create this recommendation.',
    )
    for description in primary_descriptions:
        assert f'<p class="mt-1 text-sm leading-6 text-content-secondary">{description}</p>' in modal
