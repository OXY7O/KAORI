import re
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
    assert 'Authorized Notification-backed activity.' in summary
    assert 'System-Wide Scope' not in summary
    assert 'Actor, role and source recorded at commit.' in summary
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

    assert 'Hot PostgreSQL; verified Data Lifecycle archive.' in summary
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
    assert re.search(r'db\.session\.add\(\s*AuditEvent\(', handoff)

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
    # Deny links unless one of the separately permissioned committed sources is visible.
    assert 'if not can_view_jobs and not can_view_tenants and not can_view_deliveries:' in links
    assert 'if can_view_deliveries:' in links
    assert "metadata.get('job_public_id')" in links
    assert 'JobExecution.query.filter_by(public_id=job_id).first()' in links
    assert "url_for('jobs.executions', execution_tab='registry', search=job_id)" in links
    assert "metadata.get('tenant_audit_evidence_id')" in links
    assert 'TenantAuditEvidence.query.filter_by(public_id=evidence_id).first()' in links
    assert "url_for('tenant.tenant_detail', tenant_id=evidence.tenant_id)" in links
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'No duplicate event is created.' in detail


def test_activity_source_link_to_delivery_requires_permission_and_exact_committed_event() -> None:
    routes = read('app/access/activity_audit/routes.py')
    links = read('app/access/activity_audit/source_links.py')

    assert "current_user.has_permission('integrations.manage')" in routes
    assert "metadata.get('delivery_event_key') or metadata.get('event_key')" in links
    assert 'NotificationDelivery.query.filter_by(event_key=delivery_key).first()' in links
    assert "url_for('notification_channels.index', tab='delivery', delivery_event_key=delivery_key)" in links
    assert 'can_view_deliveries: bool = False' in links
    assert 'Never infer delivery from a shared domain' in links


def test_activity_audit_administrative_source_scope_is_read_only_and_permission_bound() -> None:
    routes = read('app/access/activity_audit/routes.py')
    source = read('app/access/activity_audit/administrative_sources.py')
    partial = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')

    assert "@bp.get('/administrative-evidence')" in routes
    assert "current_user.has_permission('jobs.view')" in routes
    assert "current_user.has_permission('tenant.manage')" in routes
    assert 'build_administrative_evidence_context(' in routes
    assert 'if evidence is None:' in routes
    assert 'abort(403)' in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "'automatic-jobs': {" in source
    assert "'tenant-sync': {" in source
    assert "AuditEvent.action.startswith(specification['prefix'], autoescape=True)" in source
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in routes
    assert "AuditEvent.target_type.in_(specification['target_types'])" in source
    assert 'paginate_query(query, page=page, per_page=normalized_per_page)' in source
    assert 'if selected not in available:' in source
    # The visible page is resolved in one permission-gated batched lookup;
    # restoring an N+1 query would be a regression, not a contract repair.
    assert "event.target_type == 'job_execution' and event.target_id" in source
    assert 'JobExecution.public_id.in_(job_ids)' in source
    assert 'if can_view_jobs and job_ids' in source
    assert 'job = hot_jobs.get(str(event.target_id))' in source
    assert 'JobExecution.query.filter_by(public_id=event.target_id).first()' not in source
    assert 'redact_operational_text(event.summary, limit=255)' in source
    assert 'FK only (not a snapshot)' in source
    assert 'metadata_json' not in partial
    assert 'data-activity-evidence-source="administrative-audit-events"' in partial
    assert 'administrative_evidence.rows' in partial
    assert 'administrative_evidence.scope_options' in partial
    assert 'aria-label="Separate administrative AuditEvent register"' in partial
    assert 'registry_ui.filter_form(' in partial
    assert "'activity-administrative-evidence'," in partial
    assert 'No Administrative Source Evidence' in partial
    workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')
    assert "{% if selected_audit_tab == 'administrative' %}" in workspace
    assert 'Administrative Evidence' in workspace
    assert 'Activity Register' in workspace


def test_activity_audit_inventory_hierarchy_and_shared_two_tab_workspace() -> None:
    page = read('app/templates/access/activity_audit/index.html')
    workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')
    activity_card = read('app/templates/access/activity_audit/partials/_activity_table_card.html')
    activity_rows = read('app/templates/access/activity_audit/partials/_activity_table_content.html')
    administrative = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    source = read('app/access/activity_audit/administrative_sources.py')
    routes = read('app/access/activity_audit/routes.py')
    tabs = read('app/templates/components/framed_workspace_tabs.html')

    assert 'components/section_intro.html' in page
    assert "'Audit Records'" in page
    assert "'audit-records-heading'" in page
    assert 'Audit Evidence Overview' not in page  # overview belongs to the existing summary partial
    assert page.index('_activity_summary_cards.html') < page.index('_audit_records_workspace.html')
    assert page.count('_audit_records_workspace.html') == 1
    assert "'Activity Register', 'list-filter'" in workspace
    assert "'Administrative Evidence', 'file-clock'" in workspace
    assert 'framed_tabs.render_navigation(' in workspace
    assert "hx_target='#activity-audit-records'" in workspace
    assert "hx_select='#activity-audit-records'" in workspace
    assert 'selected_audit_tab' in workspace
    assert 'data-kaori-tab-variant="framed-workspace-v2-server"' in tabs
    assert workspace.count('_activity_table_card.html') == 1
    assert workspace.count('_administrative_evidence.html') == 1
    assert 'embedded|default(false)' in activity_card
    assert 'embedded|default(false)' in administrative
    assert 'name="view" value="activity"' in activity_card
    assert "'view': 'activity'" in activity_rows
    assert 'name="view" value="activity"' in activity_rows
    assert 'name="view" value="administrative"' in administrative
    assert 'name="admin_scope"' in administrative
    assert 'Source Scope' in administrative
    assert 'administrative_evidence.scope_options' in administrative
    assert 'table_ui.inventory_filter_bar_classes()' in administrative
    assert "table_ui.title_cell(row.display_action, row.summary, 'file-clock')" in administrative
    assert 'table_label.status_label(row.status_label, row.status_tone)' in administrative
    assert 'Source / Actor' in administrative
    assert 'row.actor_reference' in administrative
    assert 'Actor Reference</th>' not in administrative
    assert "table_ui.table_classes('min-w-[72rem]')" in administrative
    assert "table_label.metadata_label(row.source_label, 'database')" in administrative
    assert "page_param='admin_page'" in administrative
    assert 'registry_ui.footer(' in administrative
    assert "per_page_param='admin_per_page'" in administrative
    assert 'metadata_json' not in administrative
    assert "'display_action': display_action" in source
    assert 'job_operation_label(job.operation)' in source
    assert 'redact_operational_text(' in source
    assert 'display_action = f\'{specification["label"]}' in source
    assert 'action_suffix.replace("_", " ").title()' in source
    assert "'status_tone': status_tone" in source
    assert "'actor_detail': 'Actor FK · not a snapshot'" in source
    assert "action_suffix.endswith('partially_succeeded')" in source
    assert 'has_administrative_sources = can_view_jobs or can_manage_tenants' in routes
    assert "selected_audit_tab == 'administrative' and not has_administrative_sources" in routes
    assert "target == 'activity-administrative-evidence'" in routes
    assert "target == 'activity-audit-records'" in routes
    assert "context['administrative_evidence'] = build_administrative_evidence_context(" in routes
    assert "view='administrative'" in routes


def test_activity_audit_tab_navigation_preserves_independent_permissions_and_fallback() -> None:
    routes = read('app/access/activity_audit/routes.py')
    administrative = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')

    assert "@permission_required('activity_audit.view')" in routes
    assert "current_user.has_permission('jobs.view')" in routes
    assert "current_user.has_permission('tenant.manage')" in routes
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in routes
    assert 'if not is_htmx:' not in workspace  # server selection, no client-only tab switching
    assert 'has_administrative_sources' in workspace
    registry = read('app/templates/components/table_registry.html')
    assert 'registry_ui.filter_form(' in administrative
    assert "form_id='administrative-evidence-filter-form'" in administrative
    assert "aria_label='Administrative source filters'" in administrative
    assert 'method="GET"' in registry
    assert 'hx-push-url="true"' in registry
    assert 'hx-target="#{{ registry_id }}"' in registry
    assert 'hx-sync="closest section:replace"' in registry
    assert 'data-activity-evidence-source="administrative-audit-events"' in administrative


def test_activity_audit_framed_tabs_and_canonical_administrative_filters() -> None:
    workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')
    admin = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    source = read('app/access/activity_audit/administrative_sources.py')
    routes = read('app/access/activity_audit/routes.py')
    framed = read('app/templates/components/framed_workspace_tabs.html')
    registry = read('app/templates/components/table_registry.html')
    loading = read('app/templates/components/loading_bar.html')

    assert 'framed_tabs.render_navigation(' in workspace
    assert 'content_tabs.render_links(' not in workspace
    assert 'data-kaori-tab-variant="framed-workspace-v2-server"' in framed
    assert "hx_target='#activity-audit-records'" in workspace
    assert 'registry_ui.filter_form(' in admin
    assert "'activity-administrative-evidence'," in admin
    assert 'data-kaori-canonical-registry-filter="{{ registry_id }}"' in registry
    assert 'table_primitives.filter_layout_classes()' in registry
    assert "classes='w-full'" in admin
    assert "'admin_search'" in admin
    assert 'name="admin_scope"' in admin
    assert 'name="admin_outcome"' in admin
    assert 'name="admin_time_range"' in admin
    assert "per_page_param='admin_per_page'" in admin
    assert "page_param='admin_page'" in admin
    assert 'data-kaori-clear-filters' in registry
    assert 'registry_ui.clear_filters_action(' in admin
    assert "marker='activity-administrative-evidence'" in admin
    assert 'registry_ui.footer(' in admin
    assert "loading_bar.render('administrative-activity-loading'" in admin
    assert '<header class="border-b border-outline-subtle px-5 py-4 sm:px-6">' in admin
    assert 'header class="{{ table_ui.block_header_classes() }}"' not in admin
    assert admin.index("loading_bar.render('administrative-activity-loading'") < admin.index('</header>')
    assert 'aria-label="{{ aria_label }}"' in registry
    assert 'hx-indicator="#{{ loading_id }}"' in registry
    assert 'kaori-loading-bar-segment' in loading
    assert "page_param='admin_page'" in admin
    assert "per_page_param='admin_per_page'" in admin
    assert '<noscript>' in admin
    assert 'AuditEvent is hot, source-owned evidence.' not in admin
    assert "AuditEvent.action.startswith(specification['prefix'], autoescape=True)" in source
    assert 'AuditEvent.action.icontains(normalized_search, autoescape=True)' in source
    assert 'AuditEvent.summary.icontains(normalized_search, autoescape=True)' in source
    assert 'AuditEvent.target_id.icontains(normalized_search, autoescape=True)' in source
    assert "AuditEvent.action.endswith('_partially_succeeded', autoescape=True)" in source
    assert 'AuditEvent.created_at >= datetime.now(UTC) - _TIME_DELTA[normalized_time_range]' in source
    assert 'normalize_per_page(per_page)' in source
    assert 'paginate_query(query, page=page, per_page=normalized_per_page)' in source
    assert 'selected != available[0]' in source
    assert "current_user.has_permission('jobs.view')" in routes
    assert "current_user.has_permission('tenant.manage')" in routes
    assert "if selected_audit_tab == 'administrative' and not has_administrative_sources:" in routes
    for param in ('admin_search', 'admin_outcome', 'admin_time_range', 'admin_per_page'):
        assert f"request.args.get('{param}'" in routes or f"_request_int('{param}'" in routes


def test_uat_administrative_evidence_uses_shared_title_result_count() -> None:
    administrative = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    header = administrative.split('</header>', 1)[0]
    assert header.index('>Administrative Source Evidence</h2>') < header.index(
        'table_label.result_count(administrative_evidence.pagination.total_items)'
    )
    assert header.count('table_label.result_count(') == 1
    assert '{{ administrative_evidence.pagination.total_items }} Recorded' not in header
    assert 'registry_ui.clear_filters_action(' in header
    assert "loading_bar.render('administrative-activity-loading'" in header


def test_activity_audit_registers_use_shared_accessible_source_hover_info() -> None:
    activity = read('app/templates/access/activity_audit/partials/_activity_table_card.html')
    administrative = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    shared = read('app/templates/components/info_tip.html')
    workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')

    for fragment in (activity, administrative):
        assert '{% import "components/info_tip.html" as info_tip %}' in fragment
        assert fragment.count('info_tip.render(') == 1
        assert fragment.count("variant='guide'") == 1
        # Title-level context must be a Guide; default icon remains for fields only.
    activity_header = activity.split('</header>', 1)[0]
    admin_header = administrative.split('</header>', 1)[0]
    assert (
        activity_header.index('>Activity Register</h2>')
        < activity_header.index("'activity-audit-register-source-info'")
        < activity_header.index('table_label.result_count(pagination.total)')
    )
    assert (
        admin_header.index('>Administrative Source Evidence</h2>')
        < admin_header.index("'activity-audit-administrative-source-info'")
        < admin_header.index('table_label.result_count(administrative_evidence.pagination.total_items)')
    )

    assert 'Activity Register Evidence' in activity
    assert 'Hot committed Notification-backed operational activity' in activity
    assert 'Actor identity is snapshotted' in activity
    assert 'this register is not an archived-record search' in activity
    assert 'Separate permission-scoped hot AuditEvent' in administrative
    assert 'Automatic Jobs and Tenant Inventory Sync remain source-owned' in administrative
    assert 'source foreign key, not an immutable actor snapshot' in administrative
    assert 'Archive browsing lists bundles only' in administrative

    assert 'data-kaori-info-tip-trigger' in shared
    assert 'aria-expanded="false"' in shared
    assert 'role="tooltip"' in shared
    assert 'focus-visible:ring-2' in shared
    assert "selected_audit_tab == 'administrative'" in workspace
    assert 'registry_ui.clear_filters_action(' in activity
    assert 'registry_ui.clear_filters_action(' in administrative
    assert activity.count('table_label.result_count(') == 1
    assert administrative.count('table_label.result_count(') == 1
