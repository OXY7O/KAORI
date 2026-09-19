from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_notification_progress_track_uses_one_shared_full_width_geometry() -> None:
    progress = read('app/templates/components/progress_bar.html')

    assert '{% macro notification_track_classes()' in progress
    assert 'h-1.5 w-full overflow-hidden rounded-full' in progress
    assert 'notification_progress(value' in progress
    assert 'notification_indeterminate(label' in progress
    assert 'track_classes=notification_track_classes()' in progress
    assert 'class="{{ notification_track_classes() }}"' in progress


def test_notification_progress_fill_remains_proportional_to_actual_job_progress() -> None:
    progress = read('app/templates/components/progress_bar.html')

    assert 'data-progress="{{ safe_value }}"' in progress
    assert 'style="width: {{ safe_value }}%"' in progress
    assert 'w-full min-w-0' in progress
    assert 'notification_progress(job.progress, label=label)' in progress


def test_notification_deck_does_not_override_shared_progress_track_width() -> None:
    activity = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')

    assert 'progress_bar.job_progress(' in activity
    assert '<div class="mt-2 w-full">' in activity
    assert 'style="width:' not in activity
