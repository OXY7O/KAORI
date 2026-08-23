from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resolved_verification_closure_is_a_compact_governed_card() -> None:
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')

    for marker in (
        'data-alert-verification-closure',
        'data-alert-verification-fields',
        'data-alert-verification-references',
        'data-alert-verification-actions',
    ):
        assert marker in modal

    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card' in modal
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in modal
    assert 'lg:grid-cols-12' in modal
    assert 'lg:col-span-6' in modal
    assert 'lg:col-span-8' in modal
    assert 'lg:col-span-4' in modal
    assert 'Operational References' in modal
    assert 'Verify & Close' in modal


def test_verification_closure_keeps_status_near_header_and_action_in_footer() -> None:
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    section = modal.split('data-alert-verification-closure', 1)[1].split('</section>', 1)[0]

    assert "table_label.status_label('Verification Pending', 'warning', size='compact')" in section
    assert section.index('Verification & Closure') < section.index('data-alert-verification-fields')
    assert section.index('data-alert-verification-fields') < section.index('data-alert-verification-actions')
    assert section.index('data-alert-verification-actions') < section.index('Verify & Close')


def test_verification_closure_copy_and_fields_are_operationally_compact() -> None:
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')

    assert (
        'Confirm recovery evidence, record the remediation, then close the case and queue resolved delivery.' in modal
    )
    assert 'What resolved the alert and what changed?' in modal
    assert 'What evidence confirms the source recovered?' in modal
    assert 'One step per line' in modal
    assert 'CHG-12345' in modal
    assert 'INC-12345' in modal

    # The old flat two-column form caused the oversized, visually detached layout.
    assert 'class="mt-4 grid gap-3 lg:grid-cols-2"' not in modal
