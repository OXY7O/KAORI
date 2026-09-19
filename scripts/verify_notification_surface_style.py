#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        raise RuntimeError(f'Missing required file: {path}')
    return target.read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    progress = read('app/templates/components/progress_bar.html')
    progress_toast = read('app/templates/components/operational_progress_toast.html')
    operational_toast = read('app/templates/components/operational_toast.html')
    activity_items = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    loading = read('app/templates/components/loading_bar.html')
    general = read('app/templates/settings/general/partials/_page_content.html')
    account = read('app/templates/settings/account/partials/_page_content.html')

    require(
        '{% macro notification_track_classes()' in progress,
        'Shared notification progress track macro is missing',
        errors,
    )
    require(
        'h-1.5 w-full overflow-hidden rounded-full' in progress,
        'Notification progress track must use the canonical h-1.5 height',
        errors,
    )
    require(
        'notification_progress(job.progress' in progress,
        'Job progress must use the shared notification progress macro',
        errors,
    )
    require(
        'notification_indeterminate(' in progress,
        'Indeterminate job progress must use the shared notification macro',
        errors,
    )
    require(
        'progress_bar.notification_progress(' in progress_toast,
        'Operational progress toast must use shared determinate progress styling',
        errors,
    )
    require(
        'progress_bar.notification_indeterminate(' in progress_toast,
        'Operational progress toast must use shared indeterminate progress styling',
        errors,
    )
    require(
        'progress_bar.job_progress(' in activity_items,
        'Notification Activity Center must use shared job progress rendering',
        errors,
    )
    require(
        'mt-3 h-1.5 w-24 overflow-hidden rounded-full' in operational_toast,
        'Operational toast timer must use the canonical notification h-1.5 height',
        errors,
    )
    require(
        'mt-4 h-1 overflow-hidden rounded-full' in loading,
        'Shared HTMX loading bar must keep the canonical thin h-1 loading indicator',
        errors,
    )
    require(
        'components/loading_bar.html' in general and 'general-settings-loading' in general,
        'General Settings must use the shared HTMX loading bar',
        errors,
    )
    require(
        'components/loading_bar.html' in account and 'account-settings-loading' in account,
        'Account Settings must use the shared HTMX loading bar',
        errors,
    )

    if errors:
        print('FAIL — KAORI Notification Surface Style v1')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Notification Surface Style v1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
