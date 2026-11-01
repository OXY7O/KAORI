"""Source contract for the complete Data Lifecycle DevContainer UAT authority (#2907).

This verifies test-plan completeness, not executable PostgreSQL/Celery UAT
or human acceptance. Runtime rows must remain NOT RUN until observed.
"""

from pathlib import Path

from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES

ROOT = Path(__file__).resolve().parents[3]
UAT_PATH = 'docs/operations/data-lifecycle-nine-domain-devcontainer-uat.md'


def test_nine_domain_qualification_matrix_matches_registered_adapters() -> None:
    uat = (ROOT / UAT_PATH).read_text(encoding='utf-8')
    assert len(DOMAIN_FACTORIES) == 9
    for name in DOMAIN_FACTORIES:
        assert uat.count(f'`{name}`') >= 2
    assert 'Policy ages displayed from unpersisted defaults are proposals' in uat
    assert 'source high-watermarks' in uat
    assert 'Archive Only' in uat
    assert 'no hot deletion' in uat.lower()


def test_uat_includes_all_shared_safety_and_recovery_cases_without_false_pass() -> None:
    uat = (ROOT / UAT_PATH).read_text(encoding='utf-8')
    for case_number in range(1, 21):
        assert f'DL-E2E-{case_number:02d}' in uat
    for key in (
        'canonical maintenance JobExecution',
        'SHA-256',
        'storage profile rotation',
        'source-owned',
        'protected',
        'cold purge',
        'record-level',
        'Restore',
        'HTMX',
        'NOT RUN',
        'NOT ADMITTED',
        'HOLD',
    ):
        assert key.lower() in uat.lower()
    assert '| DL-E2E-20 |' in uat
    assert '| DL-E2E-20 |' in uat.split('## 5. Per-domain operator acceptance ledger', 1)[0]


def test_uat_preserves_existing_dependency_issues_and_no_release_admission() -> None:
    uat = (ROOT / UAT_PATH).read_text(encoding='utf-8')
    for issue in (
        '#1569',
        '#1416',
        '#2847',
        '#2850',
        '#2868',
        '#2869',
        '#2870',
        '#2889',
        '#2891',
        '#2892',
        '#2906',
        '#2907',
    ):
        assert issue in uat
    assert 'Official Developer Check, Full Admission and staging/main promotion' in uat
    assert 'NOT RECORDED' in uat
    assert 'operator must preserve raw test outputs/screenshots privately' in uat
