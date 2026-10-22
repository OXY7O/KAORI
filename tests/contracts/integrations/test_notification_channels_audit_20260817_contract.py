from pathlib import Path

from jinja2 import Environment, nodes

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
    assert 'components/workspace_tabs.html' in page
    assert 'workspace_tabs.render_navigation' in page
    assert 'workspace_tabs.render_navigation(notification_tab_items,' in page
    assert '{% set notification_tab_items = [' in page
    assert 'framed_workspace_tabs' not in page
    assert "hx_target='#notification-channels-workspace'" in page
    assert "hx_select='#notification-channels-workspace'" in page
    assert page.index('workspace_tabs.render_navigation') < page.index('page_hero.shell_classes()')
    assert page.count('section_intro.render(') == 2
    assert "('overview', 'Overview', 'layout-dashboard', none," in page
    assert "('channels', 'Channels', 'send', none," in page
    assert "('delivery', 'Delivery Activity', 'history', none," in page
    for obsolete in ('Notification Delivery Overview', 'Channel Configuration & Registry', 'Committed Delivery Evidence'):
        assert obsolete not in page
    assert "section_intro.render('Delivery Contract & Ownership'" in page
    assert "section_intro.render('Delivery Journal'" in page
    assert "notification-channels-content-title" not in page
    assert page.index("table_block.inventory_block_header(") < page.index(
        "table_registry.filter_form('notification_channels.index'"
    )
    assert "loading_bar.render(loading_id, label=loading_label)" in read('app/templates/components/table.html')
    assert 'id="notification-channels-workspace"' in page


def test_notification_setup_summaries_and_ownership_remain_concise() -> None:
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    service = read('app/integrations/delivery/notification_channels/service.py')

    summaries = (
        'Use a dedicated Telegram bot and destination; keep its token encrypted in KAORI.',
        'Use an approved SMTP relay, sender identity, and operational recipients.',
        'Use a Teams Workflow webhook; legacy Office 365 connector URLs are unsupported.',
    )
    assert all(len(summary) <= 85 for summary in summaries)
    for summary in summaries:
        assert f"setup_summary='{summary}'" in providers

    assert 'Encrypt Telegram bot tokens as channel secrets' in providers
    assert 'STARTTLS, TLS/SMTPS, or an explicitly trusted relay policy.' in providers
    assert 'The Workflow trigger configured for Anyone authentication' in providers
    assert (
        "'ownership': 'Consumers emit governed events; "
        "Notification Channels handles provider delivery.'"
    ) in service


def test_notification_tab_macro_namespace_cannot_be_shadowed_by_local_assignment() -> None:
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    parsed = Environment().parse(page)
    imported_macros = {node.target for node in parsed.find_all(nodes.Import)}
    assigned_names = {
        node.target.name
        for node in parsed.find_all(nodes.Assign)
        if isinstance(node.target, nodes.Name)
    }

    assert 'workspace_tabs' in imported_macros
    assert 'workspace_tabs' not in assigned_names
    assert 'workspace_tabs.render_navigation(notification_tab_items,' in page


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
    assert "info_tip.render(" in workspace
    assert "Channel Inventory Guidance" in workspace
    assert "Operational Feedback:" in workspace
    assert "Activity Audit:" in workspace
    assert 'grid gap-4 lg:grid-cols-3' not in workspace
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
    assert 'not receipt or readership by a person.' in page
    assert 'No Matching Deliveries' in page
    assert 'No committed delivery matches the selected filters.' in page


def test_notification_delivery_journal_filters_use_committed_sql_and_canonical_table() -> None:
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    page = read('app/templates/integrations/delivery/notification_channels/index.html')
    channels = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    shared_table = read('app/templates/components/table_registry.html')

    for key in ('delivery_provider', 'delivery_domain', 'delivery_severity', 'delivery_status'):
        assert f"request.args.get('{key}', '')" in routes
        assert f'name="{key}"' in page
        assert f"'{key}': payload.delivery_filters." in page
    for predicate in (
        'NotificationDelivery.channel.has(NotificationChannel.provider_key == provider)',
        'NotificationDelivery.domain == domain',
        'NotificationDelivery.severity == severity',
        'NotificationDelivery.status == status',
    ):
        assert predicate in service
    assert "normalized_delivery_provider in _PROVIDER_LABELS" in service
    assert "normalized_delivery_domain in {item['value'] for item in domain_options()}" in service
    assert "normalized_delivery_severity in _SEVERITY_RANK" in service
    assert "normalized_delivery_status in {'queued', 'sent', 'failed', 'skipped'}" in service
    assert service.index('if status:', service.index('def _delivery_registry_page(')) < service.index(
        'rows, pagination = paginate_query(', service.index('def _delivery_registry_page(')
    )
    assert "'delivery_filters_active': any(" in service
    assert 'if payload.delivery_filters_active' in page
    assert "result_count=payload.delivery_pagination.total_items" in page
    assert "table_registry.footer('notification_channels.index'," in page
    assert "table_registry.clear_filters_link('notification_channels.index'," in page
    assert "table_block.inventory_block_header(" in page
    assert page.index("table_block.inventory_block_header(") < page.index(
        "table_registry.filter_form('notification_channels.index'"
    )
    assert "loading_bar.render(loading_id, label=loading_label)" in read('app/templates/components/table.html')
    assert 'hx-trigger="change, input changed delay:450ms"' in shared_table
    assert "section_intro.render('Configured Channels'" in channels
    assert channels.index("section_intro.render('Configured Channels'") < channels.index(
        'id="notification-channel-registry"'
    )
    assert channels.index('id="notification-channel-registry"') < channels.index(
        "table_block.inventory_block_header("
    )
    assert "header_actions=channel_clear_action" in channels
    assert "title_extra=info_tip.render(" in channels
    assert page.count("('Events', payload.delivery_contract.events") == 1
    assert "section_intro.render('Delivery Contract & Ownership'" in page
    assert "'Delivery Ownership'," not in page



def test_notification_refinement_reuses_header_info_tip_and_trailing_clear_filters() -> None:
    index = read('app/templates/integrations/delivery/notification_channels/index.html')
    channels = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    registry = read('app/templates/components/table_registry.html')
    table = read('app/templates/components/table.html')
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')

    assert "table_block.inventory_block_header(" in index
    assert "loading_bar.render(loading_id, label=loading_label)" in table
    assert "'notification-delivery-loading'" in index
    assert "lead=false" in index
    assert "header_actions=delivery_clear_action" in index
    assert "table_ui.action_classes() ~ ' ml-auto'" not in index
    assert "lead=true) -%}" in registry
    assert "lead=lead) }}" in registry
    assert "hx-indicator=\"#{{ loading_id }}\"" in registry
    assert "info_tip.render(" in channels
    assert "Channel Inventory Guidance" in channels
    assert "Validation Gate:" in channels
    assert "Operational Feedback:" in channels
    assert "Activity Audit:" in channels
    assert '<section class="grid gap-4 lg:grid-cols-3">' not in channels
    assert "operational_section_card.render(" in index
    assert index.count("integration_ui.interpretation_panel(") == 1
    assert "'Provider Accepted ≠ Recipient Read'" in index
    assert "not receipt or readership by a person." in index
    assert 'sm:divide-x sm:divide-outline-subtle' in index
    assert "Committed Delivery Journal" in index
    assert "Independent Activity Audit" in index
    assert "sending a notification does not create an audit event." in index
    assert "variant='guide'" in channels
    assert channels.index("info_tip.render(") < channels.index("variant='guide'")
    assert index.index("operational_section_card.render(") < index.index(
        "section_intro.render('Delivery Journal'"
    ) < index.index("table_block.inventory_block_header(")
    assert "Consumers choose destinations; the Alert Source governs alert routing and receivers." in index
    assert "KAORI governs credentials, validation, delivery evidence, retries and deduplication." in index
    assert "Allow ntfy HTTPS origins via NOTIFICATION_NTFY_ALLOWED_ORIGINS (app/worker); restrict egress." in providers



def test_notification_registry_headers_follow_kubernetes_inventory_clear_filter_contract() -> None:
    channels = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    delivery = read('app/templates/integrations/delivery/notification_channels/index.html')
    shared_table = read('app/templates/components/table.html')
    shared_registry = read('app/templates/components/table_registry.html')
    kubernetes = read('app/templates/kubernetes/inventory/pods/partials/_table_card.html')

    assert 'table_ui.inventory_block_header(' in kubernetes
    assert 'header_actions=inventory_header_actions' in kubernetes
    assert 'loading_bar.render(loading_id, label=loading_label)' in shared_table
    for source, action in (
        (channels, 'channel_clear_action'),
        (delivery, 'delivery_clear_action'),
    ):
        assert f'{{% set {action} = none %}}' in source
        assert f'{{% set {action} %}}' in source
        assert f'header_actions={action}' in source
        assert source.count("table_registry.clear_filters_link('notification_channels.index'") == 1
        assert source.index("table_registry.clear_filters_link('notification_channels.index'") < source.index(
            'table_block.inventory_block_header('
        ) < source.index("table_registry.filter_form('notification_channels.index'")
        assert 'table_block.inventory_filter_bar_classes()' in source
        assert 'classes=table_ui.inventory_filter_bar_classes()' not in source
    assert channels.index("title_extra=info_tip.render(") < channels.index(
        "table_registry.filter_form('notification_channels.index'"
    )
    assert "header_actions=channel_clear_action" in channels
    assert "header_actions=delivery_clear_action" in delivery
    assert "table_ui.action_classes() ~ ' ml-auto'" not in delivery
    assert 'hx-target="#{{ registry_id }}"' in shared_registry
    assert 'hx-indicator="#{{ loading_id }}"' in shared_registry
    assert "page_param='channel_page'" in channels
    assert "page_param='delivery_page'" in delivery
    assert "'tab': 'channels'" in channels
    assert "'tab': 'delivery'" in delivery
    assert delivery.count('integration_ui.interpretation_panel(') == 1
    assert "md:grid-cols-3" not in delivery


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
    assert 'func.lower(NotificationChannel.name).contains(search.lower(), autoescape=True)' in service
    assert 'NotificationChannel.provider_key == provider' in service
    assert 'NotificationChannel.enabled.is_(True)' in service
    assert 'NotificationChannel.enabled.is_(False)' in service
    assert 'query = query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc())' in service
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
    assert "table_block.inventory_block_header(" in page
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
    assert 'data-dialog-target="notification-channel-guide-dialog"' in cards
    assert 'data-dialog-target="notification-channel-config-dialog"' in cards
    assert "table_label.metadata_label('Guided Setup', icon='book-open-check')" in modals
    assert 'id="notification-channel-guide-title"' in modals
    assert 'data-kaori-dialog-close' in modals
    assert 'focus-visible:ring-outline-focus' in shared


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
    for requirement in (
        'NOTIFICATION_NTFY_ALLOWED_ORIGINS',
        'NOTIFICATION_NTFY_CA_BUNDLE',
        'Anyone',
        'GitHub Actions',
        'STARTTLS',
        'TLS/SMTPS',
    ):
        assert requirement in providers
    assert 'Test Delivery' in providers


def test_channel_inventory_rows_are_compact_and_allowed_uses_expand_accessibly() -> None:
    page = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    service = read('app/integrations/delivery/notification_channels/service.py')
    shared_table = read('app/templates/components/table.html')

    # Table retains the canonical header/loading/filter/pagination structure.
    assert "table_block.inventory_block_header(" in page
    assert "table_registry.filter_form('notification_channels.index'" in page
    assert "table_registry.footer('notification_channels.index'" in page
    assert "header_actions=channel_clear_action" in page
    assert 'loading_bar.render(loading_id, label=loading_label)' in shared_table

    # Six balanced columns; testing and delivery evidence remain distinct.
    assert page.count('scope="col"') == 6
    assert 'colspan="6"' in page
    assert '>Delivery Evidence</th>' in page
    assert '<dt class="text-xs font-semibold leading-5 text-content-muted">Last Test</dt>' in page
    assert '<dt class="text-xs font-semibold leading-5 text-content-muted">Last Delivery</dt>' in page
    assert 'channel.last_tested_at|user_datetime' in page
    assert 'channel.last_delivery_at|user_datetime' in page
    assert 'channel.last_delivery_label, channel.last_delivery_tone' in page

    # Long event policy is summarized instead of flooding the default row.
    assert 'channel.event_type_labels|join(", ")' not in page
    assert 'channel.event_type_labels[:2]' in page
    assert 'allowed_use_count = channel.event_type_labels|length' in page
    assert 'allowed_use_count > 2' in page
    assert '<details class="group min-w-0">' in page
    assert '<summary class="{{ table_ui.action_classes() }}' in page
    assert 'aria-label="Show or hide all {{ allowed_use_count }} allowed uses for {{ channel.name }}"' in page
    assert 'for event_label in channel.event_type_labels' in page
    assert 'max-h-48' in page
    assert 'No events allowed' in page
    assert 'channel.report_schedule_count' in page

    # Truncated destination/domain values remain inspectable, but secrets do not surface.
    assert 'title="{{ channel.destination_label }}"' in page
    assert 'title="{{ channel.domain_labels|join(' in page
    assert "'event_type_labels': [event_type_label(value)" in service
    assert 'credential_payload' not in page

    # Existing permitted actions, deletion guard and CSRF remain unchanged.
    assert 'if can_manage' in page
    assert "url_for('notification_channels.index', tab='channels', edit=channel.id, configure=1)" in page
    assert "url_for('notification_channels.test', channel_id=channel.id)" in page
    assert "url_for('notification_channels.delete', channel_id=channel.id)" in page
    assert 'channel.delete_blocked' in page
    assert page.count('name="csrf_token" value="{{ csrf_token() }}"') == 2


def test_review6_channel_registry_loading_follows_header_before_filters() -> None:
    source = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    registry = source.split('id="notification-channel-registry"', 1)[1]
    table_macro = read('app/templates/components/table.html')
    header = registry.index("table_block.inventory_block_header(")
    filters = registry.index("table_registry.filter_form('notification_channels.index'")
    table = registry.index('<table')
    footer = registry.index("table_registry.footer('notification_channels.index'")
    assert header < filters < table < footer
    assert "loading_bar.render(loading_id, label=loading_label)" in table_macro
    assert "loading_bar.render('notification-channel-loading'" not in registry
    assert "header_actions=channel_clear_action" in registry
    assert "table_block.inventory_filter_bar_classes()" in registry


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
    assert 'payload.domain_options|length' in source
    assert 'payload.event_type_options|length' in source
    assert 'name="domains"' in source
    assert 'name="event_types"' in source
    assert 'name="enabled"' in source
    assert 'form_channel.domains if form_channel else []' in source
    assert 'form_channel.event_types if form_channel else []' in source
    assert 'form_channel.enabled' in source
    assert 'grid gap-3 sm:grid-cols-2 xl:grid-cols-3' in source
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
