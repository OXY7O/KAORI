from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_channels_use_three_canonical_workspace_tabs() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')

    assert "_WORKSPACE_TABS = {'overview', 'channels', 'delivery'}" in routes
    assert "('overview', 'Overview', 'layout-dashboard'" in page
    assert "('channels', 'Channels', 'send'" in page
    assert "('delivery', 'Delivery Activity', 'history'" in page
    assert 'framed_workspace_tabs.render_navigation' in page
    assert 'id="notification-channels-workspace"' in page


def test_notification_channel_registries_follow_kaori_rows_contract() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    channels_workspace = read(
        'app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'
    )

    assert "request.args.get('channel_per_page', default=5, type=int)" in routes
    assert "request.args.get('delivery_per_page', default=5, type=int)" in routes
    assert 'paginate_query(query, page=page, per_page=per_page)' in service
    assert "page_param='channel_page'" in channels_workspace
    assert "per_page_param='channel_per_page'" in channels_workspace
    assert "page_param='delivery_page'" in page
    assert "per_page_param='delivery_per_page'" in page
    assert 'payload.channel_pagination.allowed_per_page' in channels_workspace
    assert 'payload.delivery_pagination.allowed_per_page' in page


def test_delivery_activity_exposes_persisted_retry_and_dedup_evidence() -> None:
    service = read('app/integrations/delivery/notification_channels/service.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')

    assert 'query = NotificationDelivery.query' in service
    assert 'query = query.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())' in service
    assert 'paginate_query(query, page=page, per_page=per_page)' in service
    assert "'attempt_count': delivery.attempt_count" in service
    assert "'provider_message_id': delivery.provider_message_id or ''" in service
    assert "'error_message': delivery.error_message or ''" in service
    for label in ('Channel', 'Event', 'Scope', 'Severity', 'Status', 'Attempts', 'Recorded', 'Evidence'):
        assert f'>{label}<' in page
    assert 'No Notification Deliveries Recorded' in page


def test_delivery_policy_catalog_is_source_controlled_and_not_duplicated_in_forms() -> None:
    catalog = read('app/integrations/delivery/notification_channels/catalog.py')
    definition = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    forms = read('app/integrations/delivery/notification_channels/forms.py')
    service = read('app/integrations/delivery/notification_channels/service.py')

    assert "expected_kind='notification_delivery_contract'" in catalog
    assert 'domains:' in definition
    assert 'events:' in definition
    assert 'block_storage' not in forms
    assert '_SUPPORTED_EVENT_TYPES' not in forms
    assert '_DOMAIN_LABELS' not in service
    assert '_EVENT_LABELS' not in service
    assert 'domain_keys()' in forms
    assert 'event_type_keys()' in forms
    assert 'domain_options()' in service
    assert 'event_type_options()' in service


def test_provider_registry_owns_transport_presentation_and_model_has_no_product_default() -> None:
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    model = read('app/models/notification_channel.py')

    assert 'transport: str' in providers
    assert 'configuration: str' in providers
    assert "transport='Bot API'" in providers
    assert "transport='SMTP'" in providers
    assert "transport='Teams Workflows'" in providers
    assert 'provider_status = {' not in service
    assert 'provider_key: Mapped[str] = mapped_column(db.String(40), nullable=False)' in model
    assert "default='telegram'" not in model
    assert 'default=list' in model


def test_provider_form_contract_is_adapter_owned_and_workspace_has_no_product_default() -> None:
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    forms = read('app/integrations/delivery/notification_channels/forms.py')
    channels_workspace = read(
        'app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'
    )
    channel_modals = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')

    assert 'form_partial: str' in providers
    assert 'form_parser: ProviderFormParser' in providers
    assert 'form_validator: ProviderFormValidator' in providers
    assert 'form_view: ProviderFormView' in providers
    assert 'adapter.form_parser(form, existing)' in forms
    assert 'errors.extend(adapter.form_validator(data))' in forms
    assert 'adapter.form_view(channel)' in forms
    assert "existing.provider_key if existing else ''" in forms
    assert 'form_channel.provider_key if form_channel else initial_provider' in channels_workspace
    assert 'Select provider' in channel_modals
    assert '{% include provider_option.form_partial %}' in channel_modals


def test_delivery_event_severity_scope_is_catalog_driven() -> None:
    catalog = read('app/integrations/delivery/notification_channels/catalog.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    definition = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')

    assert 'def event_severity_scoped(key: str) -> bool:' in catalog
    assert 'severity_scoped: true' in definition
    assert 'severity_scoped: false' in definition
    assert 'event_severity_scoped(event_type)' in service


def test_channel_deletion_preserves_delivery_evidence_and_schedule_references() -> None:
    lifecycle = read('app/integrations/delivery/notification_channels/lifecycle.py')
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    channels_workspace = read(
        'app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'
    )

    assert 'class NotificationChannelDeletionBlocked(ValueError):' in lifecycle
    assert 'NotificationDelivery.query.filter_by(channel_id=channel_id).count()' in lifecycle
    assert 'ReportSchedule.notification_channel_ids' in lifecycle
    assert 'if usage.blocked:' in lifecycle
    assert 'raise NotificationChannelDeletionBlocked(usage)' in lifecycle
    assert 'except NotificationChannelDeletionBlocked as exc:' in routes
    assert "event_type='integration.notification_channel.delete_blocked'" in routes
    assert 'channel.delete_blocked' in channels_workspace
    assert 'channel.delete_reason' in channels_workspace


def test_notification_channel_feedback_separates_toast_deck_and_activity_audit() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    workspace = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    modals = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')

    assert 'create_transient_feedback(' in routes
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in routes
    assert 'OperationalDeliveryPolicy.PERSISTENT' in routes
    assert 'queue_feedback=True' in routes
    assert "'channel_name': channel_name" in routes
    assert "'provider_key': provider_key" in routes
    assert 'Operational Feedback' in workspace
    assert 'Activity Audit' in workspace
    assert 'Test failures and blocked deletion remain visible in the Notification Deck.' in workspace
    assert 'Provider secrets never appear in Toast, Notification Deck, or Activity Audit metadata.' in modals


def test_notification_channel_activity_audit_uses_integrations_category_and_readable_event_labels() -> None:
    categories = read('app/definitions/catalogs/platform_operations/notifications/event_categories.yaml')
    event_catalog = read('app/platform_operations/notifications/event_catalog.py')

    assert '- integration.' in categories
    assert "normalized.replace('.', ' ').replace('_', ' ')" in event_catalog
    assert "'channel_name': channel_name" in read('app/integrations/delivery/notification_channels/routes.py')
    assert "'provider_key': provider_key" in read('app/integrations/delivery/notification_channels/routes.py')


def test_delivery_registry_supports_exact_source_linked_event_filter() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')

    assert "request.args.get('delivery_event_key', '')" in routes
    assert 'query.filter(NotificationDelivery.event_key == event_key)' in service
    assert "normalized_delivery_key = str(delivery_event_key or '').strip()[:255]" in service
    assert "'delivery_filter': normalized_delivery_key" in service
    assert "table_ui.search_field('delivery_event_key'" in page
    assert "table_registry.filter_form('notification_channels.index'," in page
    assert "table_registry.clear_filters_link('notification_channels.index'," in page
    assert "'notification-delivery-registry'" in page
    assert "'notification-delivery-loading'" in page
    assert "'delivery_event_key': payload.delivery_filter" in page
    assert 'Delivery attempts and channel retries are provider-delivery evidence' in page
    assert 'No Matching Deliveries' in page
    assert 'No committed channel delivery matches this exact event key.' in page


def test_report_delivery_source_link_is_exact_committed_and_permissioned() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    producer = read('app/reports/notifications.py')
    source_routes = read('app/reports/generated/routes.py')

    assert "current_user.has_permission('reports.view')" in routes
    assert 'can_view_reports: bool = False' in service
    assert "'report_source_url': _report_source_url(row, report_lookup) if can_view_reports else None" in service
    assert 'if can_view_reports' in service
    assert 'report_id not in report_lookup' in service
    assert "delivery.event_type != 'report.generated'" in service
    assert "delivery.asset_type != 'report'" in service
    assert "delivery.event_key != f'report.generated:{report_id}'" in service
    assert 'Report.query.filter(Report.id.in_(report_ids)).all()' in service
    assert 'report_id = _report_id_for_delivery(delivery)' in service
    assert "delivery.event_key != f'report.generated:{report_id}'" in service
    assert "return url_for('reports.generated_report_detail', report_id=report_id)" in service
    assert "event_key=f'report.generated:{report.id}'" in producer
    assert "@permission_required('reports.view')" in source_routes
    assert 'delivery.report_source_url' in page
    assert 'Open Report' in page

def test_review5_channels_registry_uses_canonical_filter_and_safe_server_pagination() -> None:
    template = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')

    assert "table_registry.filter_form('notification_channels.index'," in template
    assert "table_registry.clear_filters_link('notification_channels.index'," in template
    assert "form_id='notification-channel-filter-form'" in template
    assert 'name="channel_provider"' in template
    assert 'name="channel_state"' in template
    assert 'channel_search' in template
    assert "'channel_search': payload.channel_filters.search" in template
    assert 'No Matching Channels' in template
    assert 'table_label.result_count(payload.channel_pagination.total_items)' in template
    for name in ('channel_search', 'channel_provider', 'channel_state'):
        assert f"request.args.get('{name}', '')" in routes
    assert "func.lower(NotificationChannel.name).contains(search.lower(), autoescape=True)" in service
    assert "NotificationChannel.provider_key == provider" in service
    assert "NotificationChannel.enabled.is_(True)" in service
    assert "NotificationChannel.enabled.is_(False)" in service
    assert "query = query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc())" in service
    assert 'paginate_query(query, page=page, per_page=per_page)' in service
    assert "request.args.get('channel_per_page', default=5, type=int)" in routes

def test_review5_delivery_activity_auto_htmx_filter_has_no_search_button() -> None:
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    canonical = read('app/templates/components/table_registry.html')
    assert "form_id='notification-delivery-filter-form'" in page
    assert "page_param='delivery_page'" in page
    assert "per_page_param='delivery_per_page'" in page
    assert "'tab': 'delivery', 'delivery_event_key': payload.delivery_filter" in page
    assert 'Find Deliveries' not in page
    assert '>Reset</a>' not in page
    assert "table_registry.clear_filters_link('notification_channels.index'," in page
    assert 'hx-trigger="change, input changed delay:450ms"' in canonical
    assert 'hx-indicator="#{{ loading_id }}"' in canonical
    assert 'hx-sync="closest section:replace"' in canonical
    assert "loading_bar.render('notification-delivery-loading'" in page
    assert 'No Matching Deliveries' in page
    assert "request.args.get('delivery_per_page', default=5, type=int)" in read(
        'app/integrations/delivery/notification_channels/routes.py'
    )

def test_review5_provider_card_controls_and_modal_header_are_reusable() -> None:
    cards = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    modals = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    shared = read('app/templates/components/action_button.html')
    assert 'components/table_primitives.html' in cards
    assert "table_ui.action_classes(size='header')" in cards
    assert 'aria-label="Open {{ provider.label }} setup guide"' in cards
    assert 'aria-label="Configure {{ provider.label }} notification channel"' in cards
    assert "data-dialog-target=\"notification-channel-guide-dialog\"" in cards
    assert "data-dialog-target=\"notification-channel-config-dialog\"" in cards
    assert "table_label.metadata_label('Guided Setup', icon='book-open-check')" in modals
    assert 'id="notification-channel-guide-title"' in modals
    assert 'data-kaori-dialog-close' in modals
    assert "focus-visible:ring-outline-focus" in shared

def test_review5_add_modal_has_catalog_provider_gallery_and_clear_header() -> None:
    template = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    assert "table_label.metadata_label('Edit Destination' if form_channel else 'New Destination'" in template
    assert 'Choose a Delivery Provider' not in template
    assert '{% for provider_option in payload.providers %}' in template
    assert 'Select provider' in template
    assert 'name="provider_key"' in template
    assert 'x-model="provider"' in template
    assert '{% include provider_option.form_partial %}' in template
    assert 'Telegram, Email, or Microsoft Teams' not in template
    assert 'Delivery Policy' in template
    assert 'Allowed Uses' in template
    for key in ('discord', 'slack', 'ntfy', 'telegram', 'email', 'microsoft_teams'):
        assert f"'{key}': NotificationProviderAdapter(" in providers
    for requirement in ('NOTIFICATION_NTFY_ALLOWED_ORIGINS', 'NOTIFICATION_NTFY_CA_BUNDLE',
                        'Anyone', 'GitHub Actions', 'STARTTLS', 'TLS/SMTPS'):
        assert requirement in providers
    assert 'Test Delivery' in providers

def test_review6_channel_registry_loading_follows_header_before_filters() -> None:
    source = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    registry = source.split('id="notification-channel-registry"', 1)[1]
    header = registry.index('<header')
    loading = registry.index("loading_bar.render('notification-channel-loading'")
    filters = registry.index("table_registry.filter_form('notification_channels.index'")
    table = registry.index('<table')
    footer = registry.index("table_registry.footer('notification_channels.index'")
    assert header < loading < filters < table < footer
    assert registry.count("loading_bar.render('notification-channel-loading'") == 1

def test_review6_provider_utilities_match_header_action_geometry_with_soft_hover() -> None:
    source = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    primitive = read('app/templates/components/table_primitives.html')
    assert source.count("table_ui.action_classes(size='header')") == 2
    assert "action_button.classes('secondary')" not in source
    assert 'data-lucide="book-open"' in source
    assert 'data-lucide="settings-2"' in source
    assert "size == 'header' else 'min-h-8 px-2.5'" in primitive
    assert "'min-h-9 px-3'" in primitive
    assert 'hover:bg-kaori-soft' in primitive
    assert 'hover:bg-kaori-primary' not in primitive
    assert 'aria-label="Open {{ provider.label }} setup guide"' in source
    assert 'aria-label="Configure {{ provider.label }} notification channel"' in source

def test_review6_modal_has_context_metadata_and_single_native_provider_select() -> None:
    source = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    assert "metadata_label('Integrations', icon='plug')" in source
    assert "metadata_label('Channel Configuration', icon='settings-2')" in source
    assert "metadata_label('Delivery Providers', icon='network')" in source
    assert "payload.providers|length ~ ' Setup Guides'" in source
    assert 'Choose a Delivery Provider' not in source
    assert 'Scheduled Reports and non-alert events ignore this threshold.' not in source
    assert 'name="provider_key"' in source
    assert 'x-model="provider"' in source
    assert 'Select provider' in source
    assert 'Delivery Policy' in source
    assert "payload.domain_options|length" in source
    assert "payload.event_type_options|length" in source
    assert 'name="domains"' in source
    assert 'name="event_types"' in source
    assert 'name="enabled"' in source
    assert 'form_channel.domains if form_channel else []' in source
    assert 'form_channel.event_types if form_channel else []' in source
    assert 'form_channel.enabled' in source
    assert 'grid gap-2 sm:grid-cols-2 xl:grid-cols-3' in source
    assert '{% include provider_option.form_partial %}' in source
    assert 'name="csrf_token"' in source

def test_review6_provider_guide_summaries_keep_security_coverage_and_copy_density() -> None:
    import ast

    source = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    module = ast.parse(source)
    found = {}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != 'NotificationProviderAdapter':
            continue
        values = {arg.arg: arg.value for arg in node.keywords}
        key = ast.literal_eval(values['key'])
        security = ast.literal_eval(values['security_note'])
        validation = ast.literal_eval(values['validation_note'])
        steps = ast.literal_eval(values['setup_steps'])
        found[key] = (security, validation, steps)
        assert 60 <= len(security) <= 115, key
        assert 60 <= len(validation) <= 120, key

    assert set(found) == {'discord', 'slack', 'ntfy', 'telegram', 'email', 'microsoft_teams'}
    assert 'mentions' in found['discord'][0]
    assert 'redirects' in found['discord'][0] and 'redirects' in found['slack'][0]
    assert 'no bypass' in found['ntfy'][0]
    assert 'NOTIFICATION_NTFY_ALLOWED_ORIGINS' in found['ntfy'][2][0]
    assert 'NOTIFICATION_NTFY_CA_BUNDLE' in ' '.join(found['ntfy'][2])
    assert 'topic' in found['telegram'][1]
    assert 'GitHub Actions' in ' '.join(found['telegram'][2])
    assert 'STARTTLS' in found['email'][0] and 'TLS/SMTPS' in found['email'][0]
    assert 'Anyone' in ' '.join(found['microsoft_teams'][2])
    for value in found.values():
        assert any(term in value[1] for term in ('read', 'recipient', 'receipt'))

