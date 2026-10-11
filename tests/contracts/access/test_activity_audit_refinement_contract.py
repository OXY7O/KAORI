from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_activity_audit_is_access_owned_over_shared_notification_evidence_store() -> None:
    access_init = read('app/access/__init__.py')
    routes = read('app/access/activity_audit/routes.py')
    notification_routes = read('app/platform_operations/notifications/routes.py')
    page = read('app/templates/access/activity_audit/index.html')

    assert "bp.register_blueprint(activity_audit_bp, url_prefix='/activity-audit')" in access_init
    assert "@permission_required('activity_audit.view')" in routes
    assert "@bp.get('/')" in routes
    assert "@bp.get('/<int:notification_id>/details')" in routes
    assert "@notifications_bp.get('/activity')" not in notification_routes
    assert 'app/templates/platform_operations/notifications/activity.html' not in routes
    assert '<h1 class="{{ page_hero.title_classes() }}">Activity Audit</h1>' in page
    assert "url_for('access.activity_audit.detail', notification_id=0)" in page


def test_activity_audit_uses_availability_posture_without_treating_warning_events_as_workspace_health() -> None:
    page = read('app/templates/access/activity_audit/index.html')
    summary = read('app/templates/access/activity_audit/partials/_activity_summary_cards.html')
    queries = read('app/platform_operations/notifications/queries.py')

    assert 'Evidence Availability' in page
    assert 'Events · 24H' in page
    assert 'Attention · 24H' in page
    assert 'Audit Evidence Overview' in summary
    assert 'Successful · 24H' in summary
    assert 'Actors · 24H' in summary
    assert 'Actor Evidence' in summary
    assert 'Hot Evidence Scope' in summary
    assert 'Notification-backed' in summary
    assert 'Authorized readers can review committed notification-backed activity across KAORI.' in summary
    assert 'System-Wide Scope' not in summary
    assert 'Actor identity, role, and authentication source are preserved at commit time.' in summary
    assert 'Immutable' in summary
    assert 'Hot + Archive' in summary
    assert "'posture_label': 'Available'" in queries
    assert "'attention_label': 'Attention Recorded' if attention else 'No Attention Recorded'" in queries
    assert 'func.count(func.distinct(Notification.actor_key))' in queries
    assert 'Unread' not in page


def test_activity_register_uses_immutable_actor_and_persisted_category_filters() -> None:
    card = read('app/templates/access/activity_audit/partials/_activity_table_card.html')
    content = read('app/templates/access/activity_audit/partials/_activity_table_content.html')
    routes = read('app/access/activity_audit/routes.py')
    queries = read('app/platform_operations/notifications/queries.py')
    catalog = read('app/platform_operations/notifications/event_catalog.py')

    for token in (
        'components/table.html',
        'components/loading_bar.html',
        'Activity Register',
        'Search Activity',
        'Category',
        'Status',
        'Actor',
        'Time Range',
        'table_ui.filter_layout_classes()',
        "loading_bar.render('operational-activity-loading'",
        'Refreshing Activity Register',
    ):
        assert token in card

    assert 'name="actor_key"' in card
    assert '{% for option in actor_options %}' in card
    assert "filters.time_range != '7d'" in card
    assert "time_range='7d'" in card
    assert "actor_key=request.args.get('actor_key')" in routes
    assert "time_range=request.args.get('time_range', '7d')" in routes
    assert 'Notification.actor_key == normalized_actor_key' in queries
    assert 'Notification.category_key == normalized_category' in queries
    assert 'Notification.actor_label.ilike(pattern)' in queries
    assert "('all', 'All Hot Records')" in queries
    assert '_activity_category_condition' not in queries
    assert 'def activity_category_keys()' in catalog

    for token in (
        'components/pagination.html',
        'Actor',
        'Recorded',
        'Rows Per Page',
        'Previous',
        'Next',
        "endpoint='access.activity_audit.index'",
        "url_for('access.activity_audit.detail'",
    ):
        assert token in content


def test_activity_actor_snapshot_is_immutable_and_recipient_fk_does_not_own_history() -> None:
    model = read('app/models/notification.py')
    actors = read('app/platform_operations/notifications/actors.py')
    writer = read('app/platform_operations/notifications/writer.py')
    auth_audit = read('app/access/authentication/audit.py')
    presentation = read('app/platform_operations/notifications/presentation.py')
    migration = read('migrations/versions/20260817_activity_audit_evidence_foundation.py')

    assert "db.ForeignKey('users.id', ondelete='SET NULL')" in model
    for field in ('category_key', 'actor_key', 'actor_label', 'actor_snapshot_json'):
        assert field in model
    assert "key='system:kaori'" in actors
    assert "key='unauthenticated'" in actors
    assert 'def resolve_operational_actor(' in actors
    assert 'notification.actor_snapshot_json = evidence.actor.as_json()' in writer
    assert 'notification.actor_label = evidence.actor.label' in writer
    assert 'activity.actor_snapshot_json = actor.as_json()' in auth_audit
    assert 'activity.deck_visible = False' in auth_audit
    assert 'actor_snapshot = notification.actor_snapshot_json or {}' in presentation
    assert 'user_label = str(notification.actor_label' in presentation
    assert "ondelete='SET NULL'" in migration
    assert "revision = '20260817_activity_audit_v1'" in migration


def test_activity_detail_uses_content_driven_curated_and_sensitive_safe_evidence() -> None:
    page = read('app/templates/access/activity_audit/index.html')
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    presentation = read('app/platform_operations/notifications/presentation.py')
    metadata = read('app/platform_operations/notifications/metadata.py')

    assert "dialog_max_width='max-w-6xl'" in page
    assert 'content_driven=true' in page
    for token in (
        'Activity Detail',
        'Failure Summary',
        'Execution Evidence',
        'Actor & Access',
        'Target Context',
        'Recorded Changes',
        'Trace References',
        'Technical Evidence',
        'item.created_at|user_datetime',
    ):
        assert token in detail
    assert 'open_by_default=false' in detail
    assert 'View Technical Evidence' in detail
    assert 'item.event_type ==' not in detail
    assert '_ACTIVITY_EXECUTION_EVIDENCE_KEYS' in presentation
    assert '_ACTIVITY_TECHNICAL_EVIDENCE_KEYS' in presentation
    assert 'redact_operational_text(value, limit=1200)' in presentation
    assert 'redact_operational_metadata(notification.metadata_json)' in presentation
    for token in ('password', 'secret', 'token', 'private_key', 'kubeconfig', 'credential_value'):
        assert repr(token) in metadata
    assert 'def redact_operational_metadata(' in metadata
    assert 'def redact_operational_text(' in metadata
    assert 'metadata = redact_operational_metadata(metadata) or {}' in metadata
    writer = read('app/platform_operations/notifications/writer.py')
    archive = read('app/platform_operations/data_lifecycle/retention/domains/operational_activity.py')
    assert 'notification.metadata_json = redact_operational_metadata(evidence.metadata)' in writer
    assert "'metadata': redact_operational_metadata(notification.metadata_json)" in archive
    assert 'redact_operational_text(notification.action_url' in archive
    assert 'redact_operational_text(notification.action_url' in presentation


def test_activity_hot_register_is_explicit_about_archive_lifecycle_boundary() -> None:
    summary = read('app/templates/access/activity_audit/partials/_activity_summary_cards.html')
    card = read('app/templates/access/activity_audit/partials/_activity_table_card.html')
    queries = read('app/platform_operations/notifications/queries.py')
    retention_domain = read('app/platform_operations/data_lifecycle/retention/domains/operational_activity.py')

    assert (
        'Hot records reside in PostgreSQL; verified older evidence remains in archive-first Data Lifecycle history.'
        in summary
    )
    assert 'This register reads hot PostgreSQL records.' not in summary
    assert 'hot-record time range' in card
    assert "('all', 'All Hot Records')" in queries
    assert 'All Retained' not in queries
    assert "source_model = 'notifications'" in retention_domain
    assert 'schema_version = 2' in retention_domain
    assert "'recipient_user_id': notification.user_id" in retention_domain
    assert "'actor_snapshot': dict(notification.actor_snapshot_json or {})" in retention_domain
    assert 'outerjoin(User' not in retention_domain
    assert 'from app.models.user import User' not in retention_domain


def test_activity_audit_cross_domain_store_boundaries_and_existing_tenant_bridge() -> None:
    """Prevent false Activity Audit coverage claims or duplicate provider bridges."""
    service = read('app/access/activity_audit/service.py')
    query = read('app/platform_operations/notifications/queries.py')
    routes = read('app/access/activity_audit/routes.py')
    bridge = read('app/kubernetes/tenant/audit_correlation_service.py')
    auto_jobs = read('app/platform_operations/jobs/audit.py')
    terminal_jobs = read('app/platform_operations/jobs/service.py')
    manual_jobs = read('app/platform_operations/jobs/routes.py')
    tenant_sync = read('app/kubernetes/tenant/audit.py')
    handoff = read('app/kubernetes/tenant/release_handoff_approval.py')
    outbound = read('app/integrations/delivery/notification_channels/service.py')
    decision = read('app/intelligence/automation_control/notifications.py')
    reports = read('app/reports/notifications.py')

    assert 'get_notification_activity_context(' in service
    assert 'get_notification_activity_detail(' in service
    assert 'AuditEvent' not in service
    assert 'Notification' in query
    assert "@permission_required('activity_audit.view')" in routes

    assert 'def _project_activity(evidence: TenantAuditEvidence)' in bridge
    assert 'activity = Notification()' in bridge
    assert 'activity.deck_visible = False' in bridge
    assert "'tenant_audit_evidence_id': evidence.public_id" in bridge
    assert '_project_activity(evidence)' in bridge
    assert 'idempotency_key=normalized.idempotency_key' in bridge

    assert 'event = AuditEvent()' in auto_jobs
    assert 'no Activity Audit Notification is created' in auto_jobs
    assert 'Notification()' not in auto_jobs
    assert 'event = AuditEvent()' in terminal_jobs
    assert 'record_operational_activity(' in manual_jobs
    assert 'AuditEvent()' in tenant_sync
    assert 'db.session.add(AuditEvent(' in handoff

    assert 'delivery = NotificationDelivery()' in outbound
    assert 'delivery.event_key = event.event_key' in outbound
    assert 'persist_notification(' not in outbound
    assert 'build_decision_notification_event(' in decision
    assert 'dispatch_matching_notification_event(' in decision
    assert 'event = NotificationEvent(' in reports
    assert 'dispatch_notification_event(' in reports


def test_activity_audit_additional_producer_sources_preserve_separate_authorities() -> None:
    configmaps = read('app/kubernetes/operations/configmaps/routes.py')
    secret_helper = read('app/kubernetes/operations/secrets/route_support.py')
    cluster = read('app/kubernetes/cluster/lifecycle_web.py')
    alertmanager = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/notifications.py'
    )
    minio = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')
    templates = read('app/reports/report_templates/routes.py')
    schedules = read('app/reports/schedules/routes.py')
    registry = read('app/artifact_registry/routes.py')
    automation = read('app/intelligence/automation_control/service.py')
    tls = read('app/kubernetes/governance/tls_certificates/audit.py')
    auth = read('app/access/authentication/audit.py')
    tenant = read('app/kubernetes/tenant/audit_correlation_service.py')

    for source in (configmaps, secret_helper, cluster, alertmanager, minio, templates, schedules, registry):
        assert 'record_operational_activity(' in source

    assert 'event = AuditEvent()' in automation
    assert 'event = AuditEvent()' in tls
    assert 'activity = Notification()' in auth
    assert 'activity = Notification()' in tenant
    # Direct producer-owned writes still need #1207 security review; the shared
    # Notification writer's pre-persist sanitization is not on these two paths.
    assert 'persist_notification(' not in auth
    assert 'persist_notification(' not in tenant

def test_activity_detail_links_only_permissioned_committed_source_workspaces() -> None:
    routes = read('app/access/activity_audit/routes.py')
    links = read('app/access/activity_audit/source_links.py')
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')

    assert 'build_related_source_links(' in routes
    assert "current_user.has_permission('jobs.view')" in routes
    assert "current_user.has_permission('tenant.view')" in routes
    assert "current_user.has_permission('tenant.manage')" in routes
    assert 'if not can_view_jobs and not can_view_tenants:' in links
    assert "metadata.get('job_public_id')" in links
    assert 'JobExecution.query.filter_by(public_id=job_id).first()' in links
    assert "url_for('jobs.executions', execution_tab='registry', search=job_id)" in links
    assert "metadata.get('tenant_audit_evidence_id')" in links
    assert 'TenantAuditEvidence.query.filter_by(public_id=evidence_id).first()' in links
    assert "url_for('tenant.tenant_detail', tenant_id=evidence.tenant_id)" in links
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'No duplicate event is created.' in detail
