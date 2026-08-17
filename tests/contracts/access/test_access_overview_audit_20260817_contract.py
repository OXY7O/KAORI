from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_access_overview_is_a_domain_summary_composer_not_a_persistence_owner() -> None:
    presentation = read('app/access/overview/presentation.py')
    for required in (
        'build_user_access_summary()',
        'build_identity_provider_summary()',
        "build_roles_index_context(can_manage_roles=False)['summary']",
        "build_permission_registry_snapshot()['summary']",
        'get_notification_activity_summary()',
    ):
        assert required in presentation
    for forbidden in (
        'User.query',
        'IdentityProvider.query',
        'Role.query',
        'Permission.query',
        'Notification.query',
        'db.session',
    ):
        assert forbidden not in presentation


def test_user_and_identity_provider_access_summaries_enforce_operational_guardrails() -> None:
    summary = read('app/users/access_summary.py')
    assert 'User.is_super_admin.is_(True)' in summary
    assert 'User.role_id.is_(None)' in summary
    assert "'active_super_admins': active_super_admins" in summary
    assert "'unassigned_active_users': unassigned_active_users" in summary
    assert 'identity_provider_configuration_complete(provider)' in summary
    assert 'provider.enabled and not configuration_states[provider.id]' in summary
    assert 'role_is_access_admin_level(role)' in summary
    assert 'provider.admission_values' in summary
    assert 'definition.admission_policy' in summary


def test_permission_and_activity_posture_reuse_authoritative_evidence() -> None:
    presentation = read('app/access/overview/presentation.py')
    permission_service = read('app/access/permissions/service.py')
    notification_queries = read('app/notifications/queries.py')
    assert "permission_summary['drift_count']" in presentation
    assert "'posture_label': 'Synchronized' if not drift_contracts else 'Review Required'" in permission_service
    assert 'def get_notification_activity_summary()' in notification_queries
    assert "Notification.status.in_(['warning', 'error'])" in notification_queries
    assert 'func.count(func.distinct(actor_identity))' in notification_queries


def test_access_boundaries_show_posture_without_mutation_controls() -> None:
    template = read('app/templates/access/overview/index.html')
    assert 'table_label.status_indicator_label(boundary.status_label, boundary.status_tone)' in template
    assert 'Read-only composition; posture comes from each authoritative Access workspace.' in template
    for forbidden in ('hx-post=', 'type="submit"', '<form'):
        assert forbidden not in template
