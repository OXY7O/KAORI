from pathlib import Path


def test_coverage_rows_show_status_only_and_consistent_scope_identity() -> None:
    template = Path('app/templates/components/integration_coverage_content.html').read_text(encoding='utf-8')
    assert 'row.coverage_detail' not in template
    assert 'Managed Kubernetes cluster' in template
    assert 'Managed Kubernetes cluster · {{ row.scope_key }}' not in template
    assert 'title="{{ row.scope_key }}"' not in template


def test_connection_contract_changes_explicitly_invalidate_bindings() -> None:
    lifecycle = Path('app/integrations/lifecycle.py').read_text(encoding='utf-8')
    prometheus = Path('app/prometheus/service.py').read_text(encoding='utf-8')
    alertmanager = Path('app/alertmanager/service.py').read_text(encoding='utf-8')
    assert 'def invalidate_bindings(' in lifecycle
    assert "binding.validation_status = 'validation_required'" in lifecycle
    assert 'binding.last_validated_at = None' in lifecycle
    assert 'invalidate_bindings(' in prometheus
    assert 'invalidate_bindings(' in alertmanager
