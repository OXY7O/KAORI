from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_mutations_are_presented_as_governed_reserved_plans():
    main = read('app/templates/intelligence/automation_control.html')
    partials = [
        read('app/templates/intelligence/partials/automation_control/_runbooks.html'),
        read('app/templates/intelligence/partials/automation_control/_decisions.html'),
        read('app/templates/intelligence/partials/automation_control/_operations.html'),
        read('app/templates/intelligence/partials/automation_control/_readiness.html'),
    ]

    assert 'Read-Only Governance' in main
    for content in partials:
        assert 'reserved_plan(' in content
        assert 'fieldset disabled' not in content


def test_runbook_workspace_does_not_render_a_fake_advanced_json_form():
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    assert 'Authoring & Publication Controls' in runbooks
    assert 'Runbook Library' in runbooks
    assert 'Advanced JSON' not in runbooks
    assert '<details' not in runbooks
    assert '<fieldset' not in runbooks
