from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_frontpages_use_one_coverage_gap_metric_and_safe_posture_logic() -> None:
    pages = {
        'Kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html'
        ),
        'Metrics Source': read('app/templates/integrations/observability/metrics_source/frontpage.html'),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html'
        ),
        'MinIO': read('app/templates/integrations/storage/object_storage/providers/minio/index.html'),
    }
    for provider, page in pages.items():
        assert 'Coverage Gaps' in page, provider
        assert 'Uncovered Assets' not in page, provider
        assert 'Uncovered Scopes' not in page, provider

    alertmanager = pages['Alertmanager']
    assert 'stats.ready == stats.total' in alertmanager
    assert 'stats.ready == stats.configured' not in alertmanager


def test_integrations_provider_catalog_surfaces_real_persisted_readiness() -> None:
    service = read('app/integrations/service.py')
    overview = read('app/templates/integrations/overview.html')

    for marker in (
        "'ready': ready",
        "'total': total",
        "'attention': attention",
        "'readiness_percent': round((ready / total) * 100, 1) if total else 0.0",
        "'posture_state': posture_state",
        "'posture_label': posture_label",
    ):
        assert marker in service

    for marker in (
        "available_provider_count ~ ' Providers'",
        'integration_status(item.posture_state, item.posture_label',
        '{{ item.total }}',
        '{{ item.ready }}',
        'Operational Readiness',
        'progress_bar.bar(item.readiness_percent',
        'Open Workspace',
    ):
        assert marker in overview


def test_provider_frontpage_consistency_verifier_uses_current_title_case_contract() -> None:
    verifier = read('scripts/verify_provider_frontpage_consistency.py')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert "'Pre-Save Requirements'" in verifier
    assert "'Pre-save Requirements'" not in verifier
    assert '├── Coverage Gaps' in standard
    assert 'fourth metric is always `Coverage Gaps`' in standard
    assert 'Provider Catalog shows registered count, ready count, real readiness percentage' in standard
