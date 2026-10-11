from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html'


def test_registry_projects_repositories_artifacts_have_contextual_table_help() -> None:
    source = TABLE.read_text(encoding='utf-8')
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert source.count('<thead') == 3
    assert source.count('info_tip.render(') == 10
    expected = {
        'projects': ('Visibility', 'Repositories', 'Last Observed'),
        'repositories': ('Artifacts', 'Pulls', 'Last Observed'),
        'artifacts': ('Digest', 'Tags', 'Type', 'Last Observed'),
    }
    headers = re.findall(r'<thead[^>]*>[\s\S]*?</thead>', source)
    for table, (domain, labels) in zip(headers, expected.items(), strict=True):
        for label in labels:
            assert f'>{label} {{{{ info_tip.render(\'registry-inventory-{domain}-' in table

    ids = re.findall(r"info_tip.render\('(registry-inventory-[^']+)'", source)
    assert len(ids) == 10 and len(set(ids)) == len(ids)


def test_registry_contextual_help_keeps_provider_evidence_boundaries() -> None:
    source = TABLE.read_text(encoding='utf-8')
    assert 'Not Collected is different from zero downloads.' in source
    assert 'an artifact may have multiple tags or none.' in source
    assert 'not a KAORI access decision.' in source
    assert 'does not establish current provider health.' in source
    assert "table_ui.inventory_block_header(" in source
    assert "resource_detail_modal.detail_button(" in source
    assert "hx-swap='outerHTML'" in source


def test_inventory_tooltip_uses_existing_accessible_control_and_htmx_hooks() -> None:
    component = (ROOT / 'app/templates/components/info_tip.html').read_text(encoding='utf-8')
    behavior = (ROOT / 'app/static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'data-kaori-info-tip-trigger' in component
    assert 'aria-describedby=' in component
    assert "'pointerover'" in behavior
    assert "'focusin'" in behavior
    assert "'click'" in behavior
    assert "'htmx:beforeSwap'" in behavior
