from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html'


def test_registry_guides_attach_to_resource_table_title_not_headers() -> None:
    source = TABLE.read_text(encoding='utf-8')
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert source.count('<thead') == 3
    assert source.count('info_tip.render(') == 3
    assert 'title_extra=registry_title_tip ~ result_badge' in source
    assert '{% set registry_title_tip %}' in source

    expected = {
        'projects': ('Project Visibility', 'Project Repositories', 'Project Last Observed'),
        'repositories': ('Repository Artifacts', 'Repository Pulls', 'Repository Last Observed'),
        'artifacts': ('Artifact Digest', 'Artifact Tags', 'Artifact Type', 'Artifact Last Observed'),
    }
    for domain, terms in expected.items():
        assert f"'registry-inventory-{domain}-title'" in source
        for term in terms:
            assert term in source

    for header in re.findall(r'<thead[^>]*>[\s\S]*?</thead>', source):
        assert 'info_tip.render(' not in header

    ids = re.findall(r"info_tip.render\('(registry-inventory-[^']+)'", source)
    assert len(ids) == 3 and len(set(ids)) == len(ids)


def test_registry_title_help_keeps_provider_evidence_boundaries() -> None:
    source = TABLE.read_text(encoding='utf-8')
    assert 'Not Collected is different from zero downloads.' in source
    assert 'an artifact may have multiple tags or none.' in source
    assert 'not a KAORI access decision.' in source
    assert 'does not establish current provider health.' in source
    assert "table_ui.inventory_block_header(" in source
    assert "resource_detail_modal.detail_button(" in source
    assert "hx-swap='outerHTML'" in source


def test_inventory_guide_reuses_accessible_info_tip_and_htmx_hooks() -> None:
    component = (ROOT / 'app/templates/components/info_tip.html').read_text(encoding='utf-8')
    behavior = (ROOT / 'app/static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'data-kaori-info-tip-trigger' in component
    assert 'aria-describedby=' in component
    assert "'pointerover'" in behavior
    assert "'focusin'" in behavior
    assert "'click'" in behavior
    assert "'htmx:beforeSwap'" in behavior
