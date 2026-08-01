from pathlib import Path


def test_recommendation_modal_uses_full_workspace_detail_contract():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()
    assert 'data-kaori-detail-variant="full-workspace-modal"' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert 'Finding Evidence' in template
    assert 'Recommended Action' in template
    assert 'Committed Evidence Boundary' in template


def test_shared_modal_supports_intelligence_context():
    modal = Path('app/templates/components/resource_detail_modal.html').read_text()
    javascript = Path('app/static/js/detail_rows.js').read_text()
    assert "context_label='Inventory'" in modal
    assert 'data-detail-context-label' in modal
    assert 'detailContextLabel' in javascript
