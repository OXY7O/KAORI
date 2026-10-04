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
        'Harbor': read('app/templates/integrations/registry/providers/harbor/index.html'),
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
        "'degraded': int(counts.get('degraded') or 0)",
        "'blocked': int(counts.get('blocked') or 0)",
    ):
        assert marker in service

    for marker in (
        "available_provider_count ~ ' Providers'",
        'integration_status(item.posture_state, item.posture_label',
        '{{ item.total }}',
        '{{ item.ready }}',
        'Ready Coverage',
        'progress_bar.bar(item.readiness_percent',
        'Open Workspace',
    ):
        assert marker in overview


def test_provider_frontpage_consistency_verifier_uses_current_title_case_contract() -> None:
    verifier = read('scripts/verify_provider_frontpage_consistency.py')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert "'Pre-Save Requirements'" in verifier
    assert "'Pre-save Requirements'" not in verifier
    assert "'Full Validation'" in verifier
    assert "'Core Validation'" not in verifier
    assert '├── Coverage Gaps' in standard
    assert 'fourth metric is always `Coverage Gaps`' in standard
    assert 'Provider Catalog shows registered count, ready count, real readiness percentage' in standard


def test_current_provider_shell_standard_includes_harbor() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    verifier = read('scripts/verify_provider_frontpage_consistency.py')

    for marker in (
        'Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor provider landing pages',
        'Canonical Connection Registry columns for Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor',
        'New Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor connection forms',
        'Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor expose registered identity',
        'identical geometry across Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor',
        'Kubernetes, Metrics Source, Alertmanager, MinIO, and Harbor MUST NOT copy their own registration-posture panel',
        'Orchestration, Observability, Storage, or Registry',
    ):
        assert marker in standard

    assert "'Harbor': read('app/templates/integrations/registry/providers/harbor/index.html')" in verifier
    assert "'Harbor': read(" in verifier
    assert "'app/templates/integrations/registry/providers/harbor/partials/_registry.html'" in verifier
    assert "'app/templates/integrations/registry/providers/harbor/instance_form.html'" in verifier
    assert "'app/templates/integrations/registry/providers/harbor/instance_detail.html'" in verifier


def test_provider_registration_copy_uses_full_validation_operator_terminology() -> None:
    hero = read('app/templates/integrations/components/_provider_registration_hero.html')
    registration_pages = {
        'Kubernetes': read('app/templates/kubernetes/cluster/add.html'),
        'Metrics Source': read('app/templates/integrations/observability/metrics_source/instance_form.html'),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'
        ),
        'MinIO': read('app/templates/integrations/storage/object_storage/providers/minio/instance_form.html'),
        'Harbor': read('app/templates/integrations/registry/providers/harbor/instance_form.html'),
    }

    assert 'after_save_label="Full Validation"' in hero
    assert 'after_save_description="Then establish provider readiness"' in hero
    assert 'after_save_label="Core Validation"' not in hero

    for provider, source in registration_pages.items():
        assert 'Core Validation' not in source, provider
        assert 'Full Validation' in source, provider
