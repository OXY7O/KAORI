from __future__ import annotations

import pytest

from app.platform_operations.overview import presentation


@pytest.mark.parametrize(
    ('archive_count', 'job_count', 'failed', 'enabled', 'label', 'tone'),
    [
        (0, 1, 0, 1, 'Active', 'info'),
        (1, 0, 0, 1, 'Active', 'info'),
        (2, 3, 0, 1, 'Active', 'info'),
        (1, 1, 1, 1, 'Needs Attention', 'warning'),
        (0, 0, 0, 1, 'Ready', 'normal'),
        (0, 0, 0, 0, 'Policies Disabled', 'unknown'),
    ],
)
def test_lifecycle_card_explains_active_evidence_without_double_count(
    monkeypatch, archive_count, job_count, failed, enabled, label, tone
):
    monkeypatch.setattr(
        presentation,
        'build_data_lifecycle_overview_summary',
        lambda: {
            'managed_domain_count': 7,
            'enabled_domain_count': enabled,
            'active_archive_total': archive_count,
            'active_job_total': job_count,
            'failed_archive_24h': failed,
        },
    )

    result = presentation.build_platform_operations_overview_context(
        can_jobs=False, can_data_lifecycle=True, can_kubernetes_admin=False
    )
    workspace = result['workspaces'][0]

    assert workspace['status_label'] == label
    assert workspace['status_tone'] == tone
    assert len(workspace['metrics']) == 3
    assert workspace['metrics'][1] == ('archive', 'Active Archives / Jobs', f'{archive_count} / {job_count}')
