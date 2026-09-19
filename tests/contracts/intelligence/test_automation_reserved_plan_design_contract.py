from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_control_uses_factual_governance_only_state_while_execution_is_disabled():
    main = read('app/templates/intelligence/automation_control.html')
    partials = [
        read('app/templates/intelligence/partials/automation_control/_overview.html'),
        read('app/templates/intelligence/partials/automation_control/_runbooks.html'),
        read('app/templates/intelligence/partials/automation_control/_decisions.html'),
        read('app/templates/intelligence/partials/automation_control/_operations.html'),
        read('app/templates/intelligence/partials/automation_control/_readiness.html'),
    ]

    assert 'Governance Only' in main
    assert 'Execution Disabled' in main
    for content in partials:
        assert 'reserved_plan(' not in content
        assert 'Reserved Plan' not in content
        assert 'fieldset disabled' not in content


def test_runbook_workspace_uses_validated_system_catalog_tables_and_modal_binding():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    modal = read('app/templates/intelligence/partials/automation_control/_binding_configuration_modal.html')
    assert 'Runbook &amp; Binding Snapshot' in runbooks
    assert 'System Runbook Catalog' in runbooks
    assert 'Activate System Runbook' in runbooks
    assert 'Activated Runbook Library' in runbooks
    assert 'Alert & Rule Bindings' in runbooks
    assert 'New Binding' in runbooks
    assert 'Create Binding' in modal
    assert 'Create Runbook' not in runbooks
    assert 'Create Revision' not in runbooks
    assert 'Publish Revision' not in runbooks
    assert '<fieldset' not in runbooks
