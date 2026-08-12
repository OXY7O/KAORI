from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    provider_pages = {
        'Kubernetes': read('app/templates/integrations/kubernetes.html'),
        'Prometheus': read('app/templates/integrations/prometheus.html'),
        'Alertmanager': read('app/templates/integrations/alertmanager.html'),
        'MinIO': read('app/templates/minio/index.html'),
    }
    shared_overview = read('app/templates/integrations/components/_provider_frontpage.html')
    shared_tabs = read('app/templates/components/integration_workspace_tabs.html')
    minio_coverage = read('app/templates/minio/partials/_coverage_content.html')
    minio_registry = read('app/templates/minio/partials/_registry_content.html')
    kubernetes_registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    for provider, page in provider_pages.items():
        assert 'integrations/components/_provider_frontpage.html' in page, provider
        assert 'components/integration_workspace_tabs.html' in page, provider
        assert 'Operational Integration' in page, provider
        assert 'Registered Connections' in page, provider
        assert 'Ready Connections' in page, provider
        assert 'Consumer Bindings' in page, provider
        assert 'Register Connection' in page, provider
        assert 'provider_front.overview(' in page, provider
        assert 'integration_tabs.render(' in page, provider

    for marker in ('Integration Contract', 'Consumer Resolution', 'Authority Boundary'):
        assert marker in shared_overview
    for marker in ('Integration Coverage', 'Connection Registry'):
        assert marker in shared_tabs

    for content in (minio_coverage, minio_registry):
        assert 'components/states/_empty_state.html' in content
        assert 'provider_registry.pagination_footer(' in content
        assert 'table_ui.table_classes(' in content

    assert '<input type="hidden" name="tab" value="registry">' in kubernetes_registry
    assert '## Provider Front Page Contract' in workspace_standard
    assert (
        'Kubernetes `Operational Readiness Paths` remains valid provider-specific coverage evidence'
        in workspace_standard
    )

    print('PASS — KAORI provider front pages share one canonical Hero, overview, coverage, and registry hierarchy.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
