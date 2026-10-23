"""Archive History Verify progressive-enhancement and safety contract (#2972)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/platform_operations/data_lifecycle/routes.py'
HISTORY = ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_history.html'


def test_verify_renders_targeted_fragment_only_for_htmx_and_full_page_for_browser() -> None:
    routes = ROUTES.read_text(encoding='utf-8')
    handler = routes.split('def verify(archive_id: str)', 1)[1].split(
        "@bp.get('/archives/<archive_id>/download')", 1
    )[0]
    assert "@permission_required('platform_operations.manage_data_lifecycle')" in routes
    assert "verify_lifecycle_archive(archive_id=archive_id, user_id=current_user.id)" in handler
    assert "except PermissionError:" in handler
    assert "abort(403, description='AuditEvent source verification access is not admitted.')" in handler
    assert "context = _context(feedback=feedback)" in handler
    assert "context['active_tab'] = 'history'" in handler
    assert "if request.headers.get('HX-Request') == 'true':" in handler
    fragment = "return render_template('platform_operations/data_lifecycle/partials/_history.html', lifecycle=context)"
    full_page = "return render_template('platform_operations/data_lifecycle/index.html', lifecycle=context)"
    assert fragment in handler
    assert full_page in handler
    assert handler.index("if request.headers.get('HX-Request') == 'true':") < handler.index(fragment)
    assert handler.index(fragment) < handler.index(full_page)
    assert handler.count('verify_lifecycle_archive(') == 1


def test_history_verify_action_preserves_filters_csrf_and_shared_feedback() -> None:
    history = HISTORY.read_text(encoding='utf-8')
    Environment().parse(history)
    assert 'hx-target="#data-lifecycle-history"' in history
    assert "url_for('platform_operations.data_lifecycle.verify', archive_id=archive.id)" in history
    assert 'name="csrf_token" value="{{ csrf_token() }}"' in history
    for name in (
        'archive_domain', 'archive_status', 'archive_trigger', 'archive_mode',
        'archive_storage', 'archive_search', 'archive_page', 'archive_per_page',
    ):
        assert f'name="{name}"' in history
    assert "{% include 'components/operation_feedback_oob.html' %}" in history
    assert "current_user.has_permission('platform_operations.manage_data_lifecycle')" in history
    assert "archive.domain != 'audit_event'" in history
