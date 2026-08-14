from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_control_uses_factual_governance_only_state_while_mutations_are_disabled():
    main = read('app/templates/intelligence/automation_control.html')
    partials = [
        read('app/templates/intelligence/partials/automation_control/_overview.html'),
        read('app/templates/intelligence/partials/automation_control/_runbooks.html'),
        read('app/templates/intelligence/partials/automation_control/_decisions.html'),
        read('app/templates/intelligence/partials/automation_control/_operations.html'),
        read('app/templates/intelligence/partials/automation_control/_readiness.html'),
    ]

    assert 'Governance Only' in main
    assert 'Mutation Disabled' in main
    for content in partials:
        assert 'reserved_plan(' not in content
        assert 'Reserved Plan' not in content
        assert 'fieldset disabled' not in content


def test_runbook_workspace_exposes_execution_eligibility_without_fake_authoring_forms():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    assert 'Runbook & Binding Posture' in runbooks
    assert 'Runbook Library' in runbooks
    assert 'Revision Execution Eligibility' in runbooks
    assert 'Alert & Rule Bindings' in runbooks
    assert 'Advanced JSON' not in runbooks
    assert '<details' not in runbooks
    assert '<fieldset' not in runbooks
