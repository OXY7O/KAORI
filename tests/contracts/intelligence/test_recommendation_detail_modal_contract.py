from pathlib import Path


def test_recommendation_detail_uses_canonical_side_drawer_hierarchy():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()
    assert 'data-kaori-detail-variant="side-drawer"' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert 'Recommendation Review' in template
    assert 'Finding Assessment' in template
    assert 'Scope & Evidence' in template
    assert 'Evidence Contract' in template
    assert 'Remediation Workflow' in template
    for phase in ('Review Evidence', 'Validate Live State', 'Apply Remediation', 'Verify & Close'):
        assert phase in template
    assert 'Target Outcome' in template
    assert 'Step {{ loop.index }} of {{ item.fix_steps|length }}' in template
    assert 'Verification Gate' in template
    assert 'absolute bottom-0 left-4 top-8 w-px' in template
    assert 'text-base font-semibold leading-6' in template
    assert 'text-[11px]' not in template
    assert 'text-[10px]' not in template


def test_shared_resource_detail_host_supports_drawer_without_main_layout_lock():
    component = Path('app/templates/components/resource_detail_modal.html').read_text()
    page = Path('app/templates/intelligence/recommendations.html').read_text()
    records = Path('app/templates/intelligence/partials/_recommendation_records.html').read_text()
    javascript = Path('app/static/js/detail_rows.js').read_text()
    app_layout = Path('app/templates/layouts/app.html').read_text()

    assert 'macro host(' in component
    for argument in ('resource_type', 'detail_url_template', 'footer_text=', 'context_label=', 'dialog_max_width='):
        assert argument in component
    assert 'data-resource-detail-presentation="{{ presentation }}"' in component
    assert "presentation == 'drawer'" in component
    assert 'translate-x-full' in component
    assert 'resource_detail_modal.drawer_host(' in page
    assert "dialog_max_width='max-w-2xl'" in page
    assert "label='Review'" in records
    assert "controls='resource-detail-drawer'" in records
    assert "modalHost.dataset.resourceDetailPresentation === 'drawer'" in javascript
    assert 'if (drawer)' in javascript
    assert 'unlockBackground()' in javascript
    assert "openFromButton(toggle, 'replace')" in javascript
    assert "if (updateHistory) updateUrl(null, 'replace')" in javascript
    assert 'history.back()' not in javascript
    assert 'event.stopPropagation()' in javascript
    assert '[scrollbar-gutter:stable]' in app_layout


def test_generated_fix_steps_follow_review_validate_apply_verify_sequence():
    presentation = Path('app/intelligence/finding_presentation.py').read_text()
    review = presentation.index("'Review the committed TLS Secret finding")
    validate = presentation.index("'Open Kubernetes Governance > TLS Secret")
    apply_change = presentation.index("'Upload the renewed tls.crt")
    verify = presentation.index("'Resync TLS inventory, validate the affected Ingress endpoint")
    assert review < validate < apply_change < verify
