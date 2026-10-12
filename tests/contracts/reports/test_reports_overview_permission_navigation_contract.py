from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_overview_hero_uses_safe_reader_fallback() -> None:
    template = read('app/templates/reports/overview/index.html')
    assert 'hero_action_url = url_for(\'reports.generated_reports\')' in template
    assert "current_user.has_permission('reports.generate')" in template
    assert "current_user.has_permission('reports.manage_storage')" in template


def test_operation_actions_are_authorized_per_target_route() -> None:
    service = read('app/reports/overview/service.py')
    body = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    for permission in ('reports.generate', 'reports.manage_schedules', 'reports.manage_storage'):
        assert f"'permission': '{permission}'" in service
    assert 'current_user.has_permission(item.permission)' in body
    assert "current_user.has_permission('reports.manage_storage')" in body
    assert "current_user.has_permission('reports.generate')" in body


def test_templates_handoff_is_permission_aware() -> None:
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')
    assert "current_user.has_permission('reports.manage_templates')" in estate
    assert "url_for('reports.generated_reports')" in estate
