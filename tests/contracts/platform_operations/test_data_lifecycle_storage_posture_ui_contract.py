"""Archive Storage evidence posture and responsive design contracts (#2977).

The tests compile Jinja and evaluate presentation states; actual endpoint,
maintenance worker and archive checksum evidence require DevContainer UAT.
"""

from pathlib import Path

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
STORAGE = ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_storage.html'
PRESENTATION = ROOT / 'app/platform_operations/data_lifecycle/retention/storage_presentation.py'


def storage_source() -> str:
    return STORAGE.read_text(encoding='utf-8')


@pytest.mark.parametrize(
    ('status', 'verified_at', 'expected_tone'),
    [
        ('reachable', None, 'info'),
        ('ready', None, 'info'),
        ('configured', None, 'info'),
        ('ready', '2026-10-24T00:00:00Z', 'normal'),
        ('verified', '2026-10-24T00:00:00Z', 'normal'),
        ('verified', None, 'warning'),
        ('unreachable', None, 'warning'),
        ('unavailable', None, 'warning'),
        ('incomplete', None, 'warning'),
    ],
)
def test_posture_tone_requires_matching_evidence_for_success(
    status: str, verified_at: str | None, expected_tone: str,
) -> None:
    source = storage_source()
    # Exercise the actual three Jinja state expressions from the template.
    state = '\n'.join(source.splitlines()[2:5]) + '\n{{ storage_tone }}'
    rendered = Environment().from_string(state).render(
        lifecycle={'storage': {'status': status, 'last_verified_at': verified_at}},
    ).strip()
    assert rendered == expected_tone


def test_storage_template_parses_and_uses_shared_semantic_labels() -> None:
    source = storage_source()
    Environment().parse(source)
    assert "table_label.status_label(lifecycle.storage.status_label, storage_tone, 'database')" in source
    assert "table_label.status_label('Verified evidence' if storage_verified" in source
    assert "'Verification pending' if storage_pending else 'Needs attention'" in source
    assert 'class="border-t border-outline-subtle pt-3"' in source
    assert 'xl:divide-x xl:divide-outline-subtle' in source
    assert 'Transport reachable only; write/read/checksum verification awaits an archive execution.' in source
    assert 'The local target is writable; archive integrity evidence is still pending.' in source
    assert 'Storage Interpretation' in source
    assert 'Last Verified' in source
    assert "'Awaiting Evidence'" in source
    assert 'storage_ready' not in source
    presenter = PRESENTATION.read_text(encoding='utf-8')
    reachable = presenter.split("if endpoint_probe['reachable']:", 1)[1].split('else:', 1)[0]
    assert "status = 'reachable'" in reachable
    assert "status_tone = 'blue'" in reachable
    assert "status_tone = 'emerald'" not in reachable


def test_archive_target_and_execution_cards_have_balanced_responsive_geometry() -> None:
    source = storage_source()
    assert source.count('xl:col-span-6') == 2
    assert 'xl:col-span-7' not in source
    assert 'xl:col-span-5' not in source
    assert 'class="grid gap-x-5 gap-y-3 p-4 sm:grid-cols-2"' in source
    assert 'sm:col-span-2' in source
    for label in (
        'Archive Target Contract', 'Execution Contract',
        'Provider', 'Location', 'Endpoint', 'Bucket', 'Worker Queue',
        'Dispatcher', 'Scheduled Run', 'Failure Recovery',
        'Purge Batch Limit', 'Worker Isolation',
    ):
        assert label in source
    for field in (
        'lifecycle.storage.provider_label', 'lifecycle.storage.location',
        'lifecycle.storage.endpoint_label', 'lifecycle.storage.bucket',
        'lifecycle.queue_name', 'lifecycle.worker.count',
        'lifecycle.scheduler_enabled', 'lifecycle.purge_batch_size',
    ):
        assert field in source


def test_source_cleanup_is_explicitly_conditional_on_governance() -> None:
    source = storage_source()
    assert 'Archive-First Safety Boundary' in source
    assert 'Hot records require verified archive evidence and source-specific cleanup admission.' in source
    assert "('4','Cleanup (if admitted)','Delete eligible rows only when authorized.')" in source
    assert "table_label.status_label('Cleanup Gated', 'info', 'shield-check')" in source
    assert 'Delete only rows inside the verified boundary.' not in source

def test_storage_has_two_primary_outlined_panels_without_repeated_inner_cards() -> None:
    source = storage_source()
    Environment().parse(source)
    # Four KPIs share a segmented strip, rather than four bordered boxes.
    summary = source.split('<section class="border-b border-outline-subtle pb-4"', 1)[1].split(
        '</section>', 1,
    )[0]
    assert 'xl:divide-x xl:divide-outline-subtle' in summary
    for label in ('Storage Readiness', 'Worker Readiness', 'Last Verified', 'Archive Format'):
        assert label in summary
    assert 'rounded-xl border' not in summary

    # Two parent contracts own the only prominent outlines.
    assert source.count('rounded-xl border border-outline-default') == 2
    execution = source.split('id="archive-execution-contract-title"', 1)[1].split(
        '</section>', 1,
    )[0]
    assert 'border-b border-outline-subtle pb-3' in execution
    assert 'rounded-lg border' not in execution
    assert 'sm:col-span-2' in execution

    # Four stages form an accessible, unboxed process strip.
    steps = source.split('id="archive-safety-boundary-title"', 1)[1].split(
        '</section>', 1,
    )[0]
    assert (
        '<ol class="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4 '
        'xl:gap-0 xl:divide-x xl:divide-outline-subtle">'
    ) in steps
    assert '<li class="min-w-0 xl:px-4 xl:first:pl-0 xl:last:pr-0">' in steps
    assert '</ol>' in steps
    assert 'rounded-lg border' not in steps
    assert 'Cleanup (if admitted)' in steps
    assert 'xl:divide-x' in steps
    assert 'xl:divide-outline-subtle' in steps
    assert 'divide-y' not in steps
    assert "rounded-lg border" not in steps
    assert (
        'Max {{ lifecycle.purge_batch_size }} expired artifacts '
        'per admitted run; retries available.'
    ) in source
    assert 'partial failures remain retryable.' not in source

    interpretation = source.split('aria-label="Storage interpretation"', 1)[0].splitlines()[-2]
    assert 'border-t border-outline-subtle pt-3' in interpretation
