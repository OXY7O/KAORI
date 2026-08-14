from __future__ import annotations

from typing import Any

from app.notification_channels.service import notification_channel_summary


def get_scheduler_context(
    storage_context: dict[str, Any],
    worker_context: dict[str, Any],
) -> list[dict[str, str]]:
    delivery = notification_channel_summary()
    return [
        {
            'label': 'Database Schedule',
            'description': (
                'Cadence, scope, sections, owner, configured channel identities, '
                'and next run time are stored with each schedule.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'database',
        },
        {
            'label': 'Reports Worker',
            'description': str(worker_context['description']),
            'status': str(worker_context['label']),
            'tone': str(worker_context['tone']),
            'icon': str(worker_context['icon']),
        },
        {
            'label': 'Artifact Storage',
            'description': str(storage_context['description']),
            'status': str(storage_context['status']),
            'tone': 'normal' if storage_context['status'] == 'Ready' else 'warning',
            'icon': 'hard-drive',
        },
        {
            'label': 'Notification Channels',
            'description': (
                'Reusable Telegram, email, and Microsoft Teams destinations are managed under Integrations.'
            ),
            'status': str(delivery['label']),
            'tone': str(delivery['tone']),
            'icon': 'send',
        },
    ]


def get_recommended_actions() -> list[str]:
    return [
        'Run the database migration before editing existing report delivery selections.',
        'Start the dedicated Reports worker and keep the Report Schedule Dispatcher enabled in Job Configuration.',
        (
            'Configure and test reusable Notification Channels under Integrations, then allow Scheduled Reports '
            'for the channels you want to use.'
        ),
        'Use Run Now to validate artifact generation, storage, and each selected channel before unattended execution.',
    ]
