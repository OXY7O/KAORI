from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_channels_use_three_canonical_workspace_tabs() -> None:
    routes = read('app/notification_channels/routes.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert "_WORKSPACE_TABS = {'overview', 'channels', 'delivery'}" in routes
    assert "('overview', 'Overview', 'layout-dashboard'" in page
    assert "('channels', 'Channels', 'send'" in page
    assert "('delivery', 'Delivery Activity', 'history'" in page
    assert 'framed_workspace_tabs.render_navigation' in page
    assert 'id="notification-channels-workspace"' in page


def test_notification_channel_registries_follow_kaori_rows_contract() -> None:
    routes = read('app/notification_channels/routes.py')
    service = read('app/notification_channels/service.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert "request.args.get('channel_per_page', default=5, type=int)" in routes
    assert "request.args.get('delivery_per_page', default=5, type=int)" in routes
    assert 'paginate_query(query, page=page, per_page=per_page)' in service
    assert "page_param='channel_page'" in page
    assert "per_page_param='channel_per_page'" in page
    assert "page_param='delivery_page'" in page
    assert "per_page_param='delivery_per_page'" in page
    assert 'payload.channel_pagination.allowed_per_page' in page
    assert 'payload.delivery_pagination.allowed_per_page' in page


def test_delivery_activity_exposes_persisted_retry_and_dedup_evidence() -> None:
    service = read('app/notification_channels/service.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert 'NotificationDelivery.query.order_by(' in service
    assert "'attempt_count': delivery.attempt_count" in service
    assert "'provider_message_id': delivery.provider_message_id or ''" in service
    assert "'error_message': delivery.error_message or ''" in service
    for label in ('Channel', 'Event', 'Scope', 'Severity', 'Status', 'Attempts', 'Recorded', 'Evidence'):
        assert f'>{label}<' in page
    assert 'No Notification Deliveries Recorded' in page


def test_delivery_policy_catalog_is_source_controlled_and_not_duplicated_in_forms() -> None:
    catalog = read('app/notification_channels/catalog.py')
    definition = read('app/definitions/catalogs/notifications/outbound_delivery.yaml')
    forms = read('app/notification_channels/forms.py')
    service = read('app/notification_channels/service.py')

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
    providers = read('app/notification_channels/providers/__init__.py')
    service = read('app/notification_channels/service.py')
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
    providers = read('app/notification_channels/providers/__init__.py')
    forms = read('app/notification_channels/forms.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert 'form_partial: str' in providers
    assert 'form_parser: ProviderFormParser' in providers
    assert 'form_validator: ProviderFormValidator' in providers
    assert 'form_view: ProviderFormView' in providers
    assert 'adapter.form_parser(form, existing)' in forms
    assert 'errors.extend(adapter.form_validator(data))' in forms
    assert 'adapter.form_view(channel)' in forms
    assert "existing.provider_key if existing else ''" in forms
    assert "form_channel.provider_key if form_channel else ''" in page
    assert 'Select provider' in page
    assert '{% include provider_option.form_partial %}' in page


def test_delivery_event_severity_scope_is_catalog_driven() -> None:
    catalog = read('app/notification_channels/catalog.py')
    service = read('app/notification_channels/service.py')
    definition = read('app/definitions/catalogs/notifications/outbound_delivery.yaml')

    assert 'def event_severity_scoped(key: str) -> bool:' in catalog
    assert 'severity_scoped: true' in definition
    assert 'severity_scoped: false' in definition
    assert 'event_severity_scoped(event_type)' in service


def test_channel_deletion_preserves_delivery_evidence_and_schedule_references() -> None:
    lifecycle = read('app/notification_channels/lifecycle.py')
    routes = read('app/notification_channels/routes.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert 'class NotificationChannelDeletionBlocked(ValueError):' in lifecycle
    assert 'NotificationDelivery.query.filter_by(channel_id=channel_id).count()' in lifecycle
    assert 'ReportSchedule.notification_channel_ids' in lifecycle
    assert 'if usage.blocked:' in lifecycle
    assert 'raise NotificationChannelDeletionBlocked(usage)' in lifecycle
    assert 'except NotificationChannelDeletionBlocked as exc:' in routes
    assert "event_type='integration.notification_channel.delete_blocked'" in routes
    assert 'channel.delete_blocked' in page
    assert 'channel.delete_reason' in page
