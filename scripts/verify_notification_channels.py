#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def main() -> int:
    errors: list[str] = []
    routes = read('app/notification_channels/routes.py')
    service = read('app/notification_channels/service.py')
    model = read('app/models/notification_channel.py')
    forms = read('app/notification_channels/forms.py')
    providers = read('app/notification_channels/providers/__init__.py')
    template = read('app/templates/integrations/notification_channels/index.html')
    integration_nav = read('app/templates/components/navigation/integrations_menu.html')
    intelligence_nav = read('app/templates/components/navigation/intelligence_menu.html')
    report_notifications = read('app/reports/notifications.py')
    report_model = read('app/models/report.py')

    checks = {
        "route ownership": "url_prefix='/integrations/notification-channels'" in routes,
        "integration permission": routes.count("@permission_required('settings.manage_integrations')") >= 5,
        "integration template": "integrations/notification_channels/index.html" in routes,
        "integration navigation": "notification_channels.index" in integration_nav,
        "removed from intelligence navigation": "notification_channels.index" not in intelligence_nav,
        "encrypted credential": 'EncryptedText()' in model,
        "provider-neutral event policy": "'report.generated'" in forms and "'alert_intelligence.active_alert'" in forms,
        "channel event persistence": 'event_types=list(data.event_types)' in service,
        "generic event dispatcher": 'def dispatch_notification_event(' in service,
        "report consumer": "REPORT_NOTIFICATION_EVENT = 'report.generated'" in report_notifications,
        "report selects channel identity": 'notification_channel_ids' in report_model and 'notification_channels:' not in report_model,
        "telegram provider": "'telegram'" in providers,
        "email provider": "'email'" in providers,
        "teams provider": "'microsoft_teams'" in providers,
        "allowed uses UI": 'Allowed Uses' in template and 'event_types' in template,
        "platform ownership copy": 'platform integration capability' in template.lower(),
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
