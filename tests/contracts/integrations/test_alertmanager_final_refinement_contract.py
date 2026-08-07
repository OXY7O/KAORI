from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_validation_is_horizontal_and_registry_is_standard_kaori_table():
    content = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    assert 'data-kaori-alertmanager-validation-decision-horizontal' in content
    assert 'data-kaori-alertmanager-capability-table' in content
    assert 'alertmanager-capability-loading' in content
    assert 'hx-indicator="#alertmanager-capability-loading"' in content
    assert 'components/pagination.html' in content
    assert 'pageSize: 5' in content
    assert '<option value="5">5</option>' in content
    assert '<option value="10">10</option>' in content
    assert '<option value="25">25</option>' in content
    assert '<option value="50">50</option>' in content
    assert 'Showing <span' in content
    assert 'Capabilities</p>' in content
    assert 'table-fixed' in content
    assert 'min-w-[62rem]' not in content
    assert 'xl:grid-cols-[minmax(0,1fr)_25rem]' not in content


def test_alertmanager_validation_modal_is_decision_first_without_repeated_evidence_cards():
    content = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    assert 'Validation Result' in content
    assert 'Latest Evidence' in content
    assert 'Success Criteria' in content
    assert 'Operational Impact' in content
    assert 'Technical Verification' in content
    assert 'Next Operational Action' in content
    assert "size='standard'" in content
    assert 'Full API Request' in content


def test_alertmanager_runtime_has_no_sticky_decision_rail_and_uses_two_full_width_surfaces():
    content = read('app/templates/alertmanager/partials/_runtime_panel.html')
    assert 'data-kaori-alertmanager-runtime-decision-horizontal' in content
    assert 'data-kaori-alertmanager-runtime-evidence' in content
    assert 'Runtime Decision' in content
    assert 'Runtime Evidence' in content
    assert 'Primary Finding' in content
    assert 'Next Operational Action' in content
    assert 'lg:sticky' not in content
    assert 'xl:sticky' not in content
    assert 'grid-cols-[minmax(0,1fr)_25rem]' not in content
    assert "truncate(150, true, '…')" in content


def test_alertmanager_binding_workspace_is_full_width_and_lifecycle_action_is_secondary():
    content = read('app/templates/alertmanager/partials/_detail_scope.html')
    assert 'data-kaori-alertmanager-binding-decision-horizontal' in content
    assert 'data-kaori-alertmanager-consumer-resolution-full-width' in content
    assert 'data-kaori-alertmanager-lifecycle-horizontal' in content
    assert 'Connection Lifecycle' in content
    assert 'Delete Connection' in content
    assert 'bg-status-critical px-4' not in content
    assert 'xl:sticky' not in content
    assert 'min-w-[76rem]' not in content
    assert 'table-fixed' in content
    assert 'table_ui.action_classes(true)' in content
