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
    template = read('app/templates/integrations/delivery/notification_channels/index.html')
    integration_nav = read('app/templates/components/navigation/integrations_menu.html')
    intelligence_nav = read('app/templates/components/navigation/intelligence_menu.html')
    report_notifications = read('app/reports/notifications.py')
    report_model = read('app/models/report.py')

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
        'delivery journal surface': 'NotificationDelivery.query.order_by(' in service
        and 'No Notification Deliveries Recorded' in template,
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
