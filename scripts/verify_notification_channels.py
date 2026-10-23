#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []
    routes = read('app/integrations/delivery/notification_channels/routes.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    lifecycle = read('app/integrations/delivery/notification_channels/lifecycle.py')
    catalog = read('app/integrations/delivery/notification_channels/catalog.py')
    definition = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    model = read('app/models/notification_channel.py')
    forms = read('app/integrations/delivery/notification_channels/forms.py')
    providers = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    template = '\n'.join(
        (
            read('app/templates/integrations/delivery/notification_channels/index.html'),
            read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'),
            read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html'),
        )
    )
    channels_template = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    channel_modals = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    channel_retire = read('app/templates/integrations/delivery/notification_channels/partials/_channel_retire_dialog.html')
    channel_details_drawer = read('app/templates/integrations/delivery/notification_channels/partials/_channel_details_drawer.html')
    channel_actions_dialog = read('app/templates/integrations/delivery/notification_channels/partials/_channel_actions_dialog.html')
    shared_side_drawer = read('app/templates/components/side_drawer.html')
    channel_policy_dialog = read('app/templates/integrations/delivery/notification_channels/partials/_channel_policy_dialog.html')
    channel_delete_blockers_dialog = read('app/templates/integrations/delivery/notification_channels/partials/_channel_deletion_blockers_dialog.html')
    native_dialogs = read('app/static/js/native_dialogs.js')
    confirmation = read('app/templates/components/destructive_confirmation_modal.html')
    confirmation_script = read('app/static/js/destructive_confirmation_modal.js')
    integration_nav = read('app/templates/components/navigation/integrations_menu.html')
    intelligence_nav = read('app/templates/components/navigation/intelligence_menu.html')
    report_notifications = read('app/reports/notifications.py')
    report_model = read('app/models/report.py')
    delivery_registry = service.partition('def _delivery_registry_page(')[2]
    delivery_registry = delivery_registry.partition('\ndef _report_id_for_delivery(')[0]
    delivery_template = read('app/templates/integrations/delivery/notification_channels/index.html')
    journal_order = 'query = query.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())'

    checks = {
        'route ownership': "url_prefix='/integrations/notification-channels'" in routes,
        'integration permission': routes.count("@permission_required('integrations.manage')") >= 5,
        'integration template': 'integrations/delivery/notification_channels/index.html' in routes,
        'integration navigation': 'notification_channels.index' in integration_nav,
        'removed from intelligence navigation': 'notification_channels.index' not in intelligence_nav,
        'encrypted credential': 'EncryptedText()' in model,
        'no implicit provider default': "default='telegram'" not in model
        and "existing.provider_key if existing else ''" in forms,
        'source-controlled event policy': "expected_kind='notification_delivery_contract'" in catalog
        and 'report.generated:' in definition
        and 'alert_intelligence.active_alert:' in definition
        and 'automation.decision_approved:' in definition
        and 'automation.decision_rejected:' in definition
        and '_SUPPORTED_EVENT_TYPES' not in forms,
        'catalog-driven severity scope': 'event_severity_scoped(event_type)' in service
        and 'severity_scoped: true' in definition,
        'provider-owned form contract': 'form_partial: str' in providers
        and 'form_parser: ProviderFormParser' in providers
        and 'form_validator: ProviderFormValidator' in providers
        and 'adapter.form_parser(form, existing)' in forms,
        'channel event persistence': 'channel.event_types = list(data.event_types)' in service,
        'generic event dispatcher': 'def dispatch_notification_event(' in service
        and 'def dispatch_matching_notification_event(' in service,
        'report consumer': "REPORT_NOTIFICATION_EVENT = 'report.generated'" in report_notifications,
        'report selects channel identity': 'notification_channel_ids' in report_model
        and 'notification_channels:' not in report_model,
        'telegram provider': "'telegram'" in providers,
        'email provider': "'email'" in providers,
        'teams provider': "'microsoft_teams'" in providers,
        'canonical workspace tabs': "_WORKSPACE_TABS = {'overview', 'channels', 'delivery'}" in routes
        and "('overview', 'Overview', 'layout-dashboard'" in template
        and "('channels', 'Channels', 'send'" in template
        and "('delivery', 'Delivery Activity', 'history'" in template,
        'integrated notification navigation': 'components/workspace_tabs.html' in delivery_template
        and 'workspace_tabs.render_navigation' in delivery_template
        and 'framed_workspace_tabs' not in delivery_template
        and delivery_template.index('workspace_tabs.render_navigation') < delivery_template.index('page_hero.shell_classes()')
        and "hx_target='#notification-channels-workspace'" in delivery_template
        and "hx_select='#notification-channels-workspace'" in delivery_template
        and delivery_template.count('section_intro.render(') == 2
        and "('overview', 'Overview', 'layout-dashboard', none," in delivery_template
        and "('channels', 'Channels', 'send', none," in delivery_template
        and "('delivery', 'Delivery Activity', 'history', none," in delivery_template
        and 'Notification Delivery Overview' not in delivery_template
        and 'Channel Configuration & Registry' not in delivery_template
        and 'Committed Delivery Evidence' not in delivery_template,
        'notification tabs macro namespace': '{% import "components/workspace_tabs.html" as workspace_tabs %}' in delivery_template
        and '{% set workspace_tabs =' not in delivery_template
        and '{% set notification_tab_items = [' in delivery_template
        and 'workspace_tabs.render_navigation(notification_tab_items,' in delivery_template,
        'delivery journal loading order': 'table_block.inventory_block_header(' in delivery_template
        and delivery_template.index('table_block.inventory_block_header(') < delivery_template.index("table_registry.filter_form('notification_channels.index'")
        and "result_count=payload.delivery_pagination.total_items" in delivery_template,
        'canonical delivery journal filters': 'delivery_filters_active' in service
        and "name=\"delivery_provider\"" in delivery_template
        and "name=\"delivery_domain\"" in delivery_template
        and "name=\"delivery_severity\"" in delivery_template
        and "name=\"delivery_status\"" in delivery_template
        and "NotificationDelivery.channel.has(NotificationChannel.provider_key == provider)" in service
        and "NotificationDelivery.domain == domain" in service
        and "NotificationDelivery.severity == severity" in service
        and "NotificationDelivery.status == status" in service
        and "result_count=payload.delivery_pagination.total_items" in delivery_template
        and "section_intro.render('Delivery Contract & Ownership'" in delivery_template
        and "section_intro.render('Configured Channels'" in template,
        'notification guidance and canonical table': "info_tip.render(" in template
        and "Channel Inventory Guidance" in template
        and "grid gap-4 lg:grid-cols-3" not in template
        and "operational_section_card.render(" in delivery_template
        and delivery_template.count("integration_ui.interpretation_panel(") == 1
        and "header_actions=channel_clear_action" in template
        and "header_actions=delivery_clear_action" in delivery_template
        and "title_extra=info_tip.render(" in template
        and "table_block.inventory_block_header(" in template
        and "table_block.inventory_filter_bar_classes()" in template
        and "table_block.inventory_filter_bar_classes()" in delivery_template
        and "table_ui.action_classes() ~ ' ml-auto'" not in delivery_template
        and "variant='guide'" in template
        and delivery_template.index("operational_section_card.render(") < delivery_template.index("section_intro.render('Delivery Journal'") < delivery_template.index("table_block.inventory_block_header(")
        and "table_block.inventory_block_header(" in delivery_template
        and "lead=false" in delivery_template
        and "not receipt or readership by a person." in delivery_template
        and "sending a notification does not create an audit event." in delivery_template,
        'confirmed HTMX channel actions': "data-destructive-modal-open" in template
        and "destructive_confirmation_modal.render(" in template
        and "data-destructive-submit-button-id=" in template
        and "data-destructive-modal-confirm" in confirmation
        and "submit?.click()" in confirmation_script
        and 'hx-target="#notification-channels-workspace"' in template
        and 'hx-select="#notification-channels-workspace"' in template
        and 'hx-get="{{ url_for(' in template
        and 'hx-post="{{ url_for(' in channel_modals
        and "target.id === 'notification-channels-workspace'" in native_dialogs
        and "operation_feedback=load_operational_feedback()" in delivery_template
        and "components/operation_feedback_oob.html" in delivery_template
        and "def _channel_return_query()" in routes
        and "delete_channel(channel)" in routes,
        'delivery journal surface': 'query = NotificationDelivery.query' in delivery_registry
        and 'query = query.filter(NotificationDelivery.event_key == event_key)' in delivery_registry
        and journal_order in delivery_registry
        and 'rows, pagination = paginate_query(query, page=page, per_page=per_page)' in delivery_registry
        and 'delivery_rows, delivery_window = _delivery_registry_page(' in service
        and "'delivery_pagination': delivery_window" in service
        and 'payload.delivery_pagination' in delivery_template
        and 'No Notification Deliveries Recorded' in delivery_template,
        'desktop-fit Channel Inventory and deletion guidance': "table_ui.table_classes('w-full min-w-[860px] table-fixed lg:min-w-0')" in channels_template
        and "channel.lifecycle_state == 'active' and can_manage" in channels_template
        and 'Locked' in channel_actions_dialog
        and 'channel.delete_blocked' in channel_actions_dialog,
        'compact native policy-dialog registry': channels_template.count('scope="col"') == 5
        and 'colspan="5"' in channels_template
        and 'View policy' not in channels_template
        and 'data-dialog-target="notification-channel-actions-{{ channel.id }}"' in channels_template
        and 'detailChannel = {{ channel.id }}' in channels_template
        and '_channel_details_drawer.html' in channels_template
        and '_channel_actions_dialog.html' in channels_template
        and "channel.event_type_labels|length" in channels_template
        and 'channel.last_delivery_at|user_datetime' in channels_template
        and "def _channel_event_type_groups(" in service
        and "'event_type_groups': _channel_event_type_groups(event_type_labels)" in service,
        'policy dialog native and secret-safe': 'side_drawer.render(' in channel_details_drawer
        and 'data-side-drawer-dialog' in shared_side_drawer
        and 'channel.event_type_groups' in channel_details_drawer
        and 'for event_label in group.events' in channel_details_drawer
        and 'channel.delivery_record_count' in channel_details_drawer
        and 'channel.report_schedule_count' in channel_details_drawer
        and 'channel.last_tested_at|user_datetime' in channel_details_drawer
        and 'channel.last_delivery_at|user_datetime' in channel_details_drawer
        and 'credential_payload' not in channel_details_drawer
        and 'credential_payload' not in channel_actions_dialog,
        'balanced policy and discoverable deletion': "table_ui.table_classes('w-full min-w-[860px] table-fixed lg:min-w-0')" in channels_template
        and 'data-dialog-target="notification-channel-delete-blockers-{{ channel.id }}"' in channel_actions_dialog
        and 'Locked' in channel_actions_dialog
        and 'data-kaori-native-dialog' in channel_delete_blockers_dialog
        and 'for schedule_name in channel.report_schedule_names' in channel_delete_blockers_dialog
        and "'report_schedule_names': list(usage.report_schedule_names)" in service
        and 'raise NotificationChannelDeletionBlocked(usage)' in lifecycle
        and 'data-destructive-modal-open' in channel_actions_dialog,
        'locked deletion lifecycle clarity': 'aria-label="Locked: view deletion dependencies for {{ channel.name }}"' in channel_actions_dialog
        and 'bg-status-warning-soft' in channel_actions_dialog
        and 'Channel already disabled' in channel_delete_blockers_dialog
        and 'both dependency counts are zero' in channel_delete_blockers_dialog
        and "table_label.status_label('Locked', 'warning'" in channel_delete_blockers_dialog
        and 'Automatic delivery is already disabled.' in channel_delete_blockers_dialog
        and 'raise NotificationChannelDeletionBlocked(usage)' in lifecycle,
        'retired channel lifecycle UI': 'framed_tabs.render_navigation(' in channels_template
        and "aria_label='Channel lifecycle views'" in channels_template
        and "hx_target='#notification-channel-registry'" in channels_template
        and "hx_select='#notification-channel-registry'" in channels_template
        and 'hx-indicator="#notification-channel-loading"' in channels_template
        and 'data-kaori-tab-variant="framed-workspace-v2-server"' in read('app/templates/components/framed_workspace_tabs.html')
        and "'channel_lifecycle': payload.channel_lifecycle" in channels_template
        and "channel.lifecycle_state == 'active' and can_manage" in channels_template
        and 'name="retirement_reason" required minlength="8" maxlength="500"' in channel_retire
        and 'channel.report_schedule_count' in channel_retire
        and "notification_channels.retire" in channel_retire
        and "NotificationChannel.query.filter_by(lifecycle_state=lifecycle)" in service
        and "'channel_lifecycle': normalized_lifecycle" in service
        and "channel.lifecycle_state == 'retired'" in channel_details_drawer
        and 'channel.retirement_reason' in channel_details_drawer,
        'compact notification lifecycle copy and row anatomy': 'table_ui.title_cell(channel.name' in channels_template
        and 'role="group" aria-label="Actions for {{ channel.name }}"' in channels_template
        and 'side_drawer.render(' in channel_details_drawer
        and 'data-kaori-native-dialog' in channel_actions_dialog
        and "channel.test_status == 'success'" in channel_details_drawer
        and 'Turn off Enabled in Edit to stop delivery.' in channel_delete_blockers_dialog
        and 'both dependency counts are zero' in channel_delete_blockers_dialog
        and 'Never erase delivery evidence.' in channel_delete_blockers_dialog
        and 'aria-label="Retirement consequences"' in channel_retire
        and 'Moves this channel to Archived (read-only).' in channel_retire
        and 'Stops future channel delivery.' in channel_retire,
        'summary inspect act channel UX': channels_template.count('scope="col"') == 5
        and 'Details' in channels_template and 'More' in channels_template
        and 'data-kaori-dialog-transition' in channel_actions_dialog
        and 'name="csrf_token" value="{{ csrf_token() }}"' in channel_actions_dialog
        and 'hx-target="#notification-channels-workspace"' in channel_actions_dialog
        and 'detailChannel === ' in channel_details_drawer
        and "channel.lifecycle_state == 'active' and can_manage" in channels_template,
        'allowed uses UI': 'Allowed Uses' in template and 'event_types' in template,
        'platform ownership copy': 'platform delivery capability' in template.lower(),
        'delivery evidence deletion guard': 'class NotificationChannelDeletionBlocked(ValueError):' in lifecycle
        and 'NotificationDelivery.query.filter_by(channel_id=channel_id).count()' in lifecycle
        and 'ReportSchedule.notification_channel_ids' in lifecycle,
    }
    for label, ok in checks.items():
        if not ok:
            errors.append(label)
    if errors:
        print('FAIL — KAORI Notification Channels')
        for error in errors:
            print(f'- {error}')
        return 1
    print('PASS — KAORI Notification Channels')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
