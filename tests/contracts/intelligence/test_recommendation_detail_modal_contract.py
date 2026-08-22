from pathlib import Path


def test_recommendation_detail_uses_approved_decision_evidence_workflow():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()

    assert 'data-kaori-detail-variant="modal"' in template
    assert 'data-kaori-detail-shell' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert template.index('data-kaori-detail-shell') < template.index('data-resource-detail-header')
    assert 'data-kaori-recommendation-review-layout="decision-evidence-workflow"' in template
    assert 'Recommendation Review' in template
    assert 'Committed Snapshot' in template
    assert '{{ item.summary }}' in template

    for section in (
        'WHY KAORI RAISED THIS',
        'RECOMMENDED OUTCOME',
        'EVIDENCE & AFFECTED ASSETS',
        'REMEDIATION WORKFLOW',
        'TRACEABILITY',
        'Verification Gate',
    ):
        assert section in template

    assert '2xl:grid-cols-12' in template
    assert '2xl:col-span-7' in template
    assert '2xl:col-span-5' in template
    assert '2xl:col-span-8' in template
    assert '2xl:col-span-4' in template
    assert 'data-kaori-recommendation-summary-strip' in template
    assert 'Faster triage' in template
    assert 'Safer changes' in template
    assert 'Verifiable closure' in template

    for phase in ('Review Evidence', 'Validate Live State', 'Apply Remediation', 'Verify & Close'):
        assert phase in template
    assert 'Step {{ loop.index }} of {{ item.fix_steps|length }}' in template
    assert "table_label.metadata_label('4-step workflow'" in template


def test_recommendation_detail_preserves_long_identifiers_without_truncation():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()

    assert 'Rule Key' in template
    assert "trace_cell('key-round', 'Rule Key', item.rule_key, true, true)" in template
    assert 'break-words [overflow-wrap:anywhere]' in template
    assert 'block truncate' not in template
    assert 'line-clamp-' not in template
    assert 'text-[11px]' not in template
    assert 'text-[10px]' not in template


def test_shared_resource_detail_host_supports_approved_wide_review_modal():
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
