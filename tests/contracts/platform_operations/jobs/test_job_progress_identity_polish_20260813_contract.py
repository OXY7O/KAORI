from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_job_identity_uses_canonical_provider_and_scope_labels() -> None:
    presentation = read('app/common/job_execution_presentation.py')
    assert "'minio': 'MinIO'" in presentation
    assert "'kubernetes': 'Kubernetes'" in presentation
    assert "if raw.lower() == 'all':" in presentation
    assert "return 'All'" in presentation
    assert "'provider_label': _provider_label(job.integration_type)" in presentation
    assert 'scope = _scope_label(raw_scope)' in presentation


def test_job_progress_tracks_have_identical_full_width_geometry() -> None:
    progress = read('app/templates/components/progress_bar.html')
    activity = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    assert '<div class="w-full min-w-0">' in progress
    assert '{% macro notification_track_classes()' in progress
    assert 'h-1.5 w-full overflow-hidden rounded-full' in progress
    assert 'notification_progress(job.progress' in progress
    assert 'notification_indeterminate(' in progress
    assert '<div class="mt-2 w-full">{{ progress_bar.job_progress(' in activity
