from pathlib import Path


def test_recommendation_modal_uses_structured_workspace_detail_contract():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()
    assert 'data-kaori-detail-variant="full-workspace-modal"' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert 'Finding Assessment' in template
    assert 'Evidence Contract' in template
    assert 'Affected Context' in template
    assert 'detail.evidence_grid(item.affected_items, columns=3' in template
    assert 'Remediation Plan' in template
    assert "['Review Evidence', 'Validate Context', 'Apply Remediation', 'Verify Outcome']" in template
    assert 'Step {{ loop.index }} of {{ item.fix_steps|length }}' in template
    assert 'Validation Gate' in template
    assert 'Recommended Outcome' in template
    assert 'lg:grid-cols-3' not in template


def test_shared_modal_supports_intelligence_context_and_page_stability():
    modal = Path('app/templates/components/resource_detail_modal.html').read_text()
    page = Path('app/templates/intelligence/recommendations.html').read_text()
    javascript = Path('app/static/js/detail_rows.js').read_text()
    app_layout = Path('app/templates/layouts/app.html').read_text()
    assert "context_label='Inventory'" in modal
    assert "dialog_max_width='max-w-[100rem]'" in modal
    assert 'data-detail-context-label' in modal
    assert 'overscroll-contain' in modal
    assert "dialog_max_width='max-w-5xl'" in page
    assert 'detailContextLabel' in javascript
    assert "lockedMain.style.overflowY = 'hidden'" in javascript
    assert "openFromButton(toggle, 'replace')" in javascript
    assert "if (updateHistory) updateUrl(null, 'replace')" in javascript
    assert 'history.back()' not in javascript
    assert 'event.stopPropagation()' in javascript
    assert '[scrollbar-gutter:stable]' in app_layout
