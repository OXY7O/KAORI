from pathlib import Path


def test_recommendation_detail_uses_casefile_action_rail_workspace():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()

    assert 'data-kaori-detail-variant="modal"' in template
    assert 'data-kaori-detail-shell' in template
    assert 'data-resource-detail-header' in template
    assert 'data-resource-detail-summary' in template
    assert template.index('data-kaori-detail-shell') < template.index('data-resource-detail-header')
    assert 'data-kaori-recommendation-review-layout="casefile-action-rail"' in template
    assert 'data-kaori-recommendation-status-rail' in template
    assert 'Recommendation Review' in template
    assert 'Committed Evidence' in template
    assert '{{ item.summary }}' in template

    for section in (
        'Case Brief',
        'Affected Resources',
        'Evidence Ledger',
        'Operator Direction',
        'Remediation Path',
        'Traceability',
        'Verification Gate',
    ):
        assert section in template

    assert '2xl:grid-cols-12' in template
    assert '2xl:col-span-8' in template
    assert '2xl:col-span-4' in template
    assert '2xl:sticky 2xl:top-4' in template
    assert 'bg-kaori-mist/50' in template
    assert 'after:bg-brand-outline' in template
    assert 'hidden bg-kaori-primary lg:block' not in template
    title_index = template.index('{{ review_title }}')
    status_index = template.index("table_label.status_label(item.severity_label, item.tone, size='compact')")
    summary_index = template.index('{{ item.summary }}')
    assert title_index < status_index < summary_index
    assert 'shrink-0 pt-5">{{ table_label.status_label(item.severity_label' not in template

    for phase in ('Review Evidence', 'Validate Live State', 'Apply Remediation', 'Verify & Close'):
        assert phase in template
    assert 'Safety checkpoint' in template


def test_recommendation_detail_preserves_long_identifiers_without_truncation():
    template = Path('app/templates/intelligence/partials/_recommendation_detail_content.html').read_text()

    assert 'Rule Key' in template
    assert 'break-all' in template
    assert 'break-words [overflow-wrap:anywhere]' in template
    assert 'block truncate' not in template
    assert 'line-clamp-' not in template
    assert 'text-[11px]' not in template
    assert 'text-[10px]' not in template


def test_shared_resource_detail_host_supports_wide_review_modal():
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
