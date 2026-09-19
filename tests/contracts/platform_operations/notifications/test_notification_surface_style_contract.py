from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_progress_surfaces_share_one_height_contract() -> None:
    progress = read('app/templates/components/progress_bar.html')
    progress_toast = read('app/templates/components/operational_progress_toast.html')
    activity_center = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    operational_toast = read('app/templates/components/operational_toast.html')

    assert '{% macro notification_track_classes()' in progress
    assert 'h-1.5 w-full overflow-hidden rounded-full' in progress
    assert 'notification_progress(job.progress' in progress
    assert 'notification_indeterminate(' in progress
    assert 'progress_bar.notification_progress(' in progress_toast
    assert 'progress_bar.notification_indeterminate(' in progress_toast
    assert 'progress_bar.job_progress(' in activity_center
    assert 'mt-3 h-1.5 w-24 overflow-hidden rounded-full' in operational_toast


def test_htmx_loading_bar_is_a_separate_thin_loading_contract() -> None:
    loading = read('app/templates/components/loading_bar.html')
    general = read('app/templates/settings/general/partials/_page_content.html')
    account = read('app/templates/settings/account/partials/_page_content.html')

    assert 'mt-4 h-1 overflow-hidden rounded-full' in loading
    assert 'components/loading_bar.html' in general
    assert 'general-settings-loading' in general
    assert 'components/loading_bar.html' in account
    assert 'account-settings-loading' in account
    assert 'verify_notification_surface_style.py' in read('scripts/quality_gate.sh')
