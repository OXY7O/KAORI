from pathlib import Path


def test_recommendation_detail_uses_canonical_layered_review_workspace():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()
    assert 'data-kaori-detail-variant="modal"' in template
    assert 'data-kaori-detail-shell' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert template.index('data-kaori-detail-shell') < template.index('data-resource-detail-header')
    assert 'Recommendation Review' in template
    assert 'data-kaori-recommendation-review-layout="layered-review-workspace"' in template
    assert 'Decision Brief' in template
    assert 'Why KAORI Raised This' in template
    assert 'Recommended Outcome' in template
    assert 'Evidence Review' in template
    assert 'Evidence Details' in template
    assert 'Remediation Workflow' in template
    assert 'Traceability' in template
    assert '{{ item.summary }}' in template
    assert 'xl:grid-cols-[minmax(0,1.4fr)_minmax(22rem,0.6fr)]' in template
    assert 'md:grid-cols-2 2xl:grid-cols-4' in template
    assert 'xl:sticky xl:top-4' not in template
    for phase in ('Review Evidence', 'Validate Live State', 'Apply Remediation', 'Verify & Close'):
        assert phase in template
    assert 'Step {{ loop.index }} of {{ item.fix_steps|length }}' in template
    assert 'Verification Gate' in template
    assert 'absolute bottom-0 left-4 top-8 w-px' not in template
    assert 'text-[11px]' not in template
    assert 'text-[10px]' not in template
    assert "trace_fact('key-round', 'Rule Key', item.rule_key, true, true)" in template
    assert 'block break-words [overflow-wrap:anywhere]' in template
    assert 'block truncate' not in template
    assert "section_heading('01'" in template
    assert "section_heading('02'" in template
    assert "section_heading('03'" in template
    assert "section_heading('04'" in template


def test_shared_resource_detail_host_supports_modal_without_main_layout_lock():
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
    assert 'resource_detail_modal.host(' in page
    assert "dialog_max_width='max-w-screen-2xl'" in page
    assert 'content_driven=false' in page
    assert "label='Review'" in records
    assert "icon='panel-right-open'" not in records
    assert "controls='resource-detail-drawer'" not in records
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
