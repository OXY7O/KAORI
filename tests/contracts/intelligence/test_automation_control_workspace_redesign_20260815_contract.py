from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_automation_control_uses_standalone_summary_and_shared_kaori_tabs():
    page = read('app/templates/intelligence/automation_control.html')
    presentation = read('app/automation_control/presentation.py')

    assert 'Automation Control Summary' in page
    assert page.index('Automation Control Summary') < page.index('Automation Control Workspace')
    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_links(' in page
    assert 'intelligence_ui.link_tabs(' not in page
    assert "'Accountable review required'" in page
    assert 'Immutable decisions requiring accountable review' not in page
    assert "('runbooks', 'Runbooks', 'book-open-check')" in presentation
    assert "('decisions', 'Decisions', 'clipboard-check')" in presentation
    assert "('operations', 'Execution', 'server-cog')" in presentation
    assert "('readiness', 'Readiness', 'shield-check')" in presentation


def test_automation_control_long_form_content_is_owned_by_one_workspace_surface():
    page = read('app/templates/intelligence/automation_control.html')
    components = read('app/templates/intelligence/partials/automation_control/_components.html')
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')

    assert 'data-automation-control-active-workspace' in page
    assert 'border-t border-outline-subtle' in components
    assert 'Control Path' in overview
    assert 'Phase 1' in overview
    assert 'Evidence & Decision Formation' in overview
    assert 'Phase 2' in overview
    assert 'Approval, Execution & Verification' in overview
    assert 'control.pipeline[:3]' in overview
    assert 'control.pipeline[3:]' in overview
    assert overview.count('lg:grid-cols-3') >= 2
    assert 'xl:grid-cols-6' not in overview
    assert 'Safety & Readiness' in overview
    assert 'Current Activity' in overview
    assert 'Decision & Execution Pipeline' not in overview
    assert 'Automation Guardrails' not in overview


def test_automation_control_preserves_governance_execution_boundaries_after_redesign():
    routes = read('app/automation_control/routes.py')
    enablement = read('app/common/automation_execution.py')
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')

    assert 'execution_enabled()' in routes
    assert 'AUTOMATION_EXECUTION_ENABLED' in enablement
    assert 'System Runbook Catalog' in runbooks
    assert 'Custom Authoring Locked' in runbooks
    assert 'Maker-Checker Required' in decisions
    assert 'Execution Handoff' in decisions
    assert 'Execution Journal' in operations
    assert 'Dead-Letter Review' in operations
    assert 'Production Enablement Gate' in readiness
    assert 'Controlled Rollout Sequence' in readiness
