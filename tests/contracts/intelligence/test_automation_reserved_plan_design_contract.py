from pathlib import Path


def test_guided_forms_are_disabled_until_logic_is_enabled():
    runbooks = Path('app/templates/intelligence/partials/automation_control/_runbooks.html').read_text()
    decisions = Path('app/templates/intelligence/partials/automation_control/_decisions.html').read_text()
    operations = Path('app/templates/intelligence/partials/automation_control/_operations.html').read_text()
    readiness = Path('app/templates/intelligence/partials/automation_control/_readiness.html').read_text()
    for content in (runbooks, decisions, operations, readiness):
        assert 'fieldset disabled' in content or 'reserved_plan(' in content
        assert 'Reserved Plan' in content


def test_advanced_json_is_secondary_and_collapsed():
    runbooks = Path('app/templates/intelligence/partials/automation_control/_runbooks.html').read_text()
    assert '<details' in runbooks
    assert 'Advanced JSON' in runbooks
