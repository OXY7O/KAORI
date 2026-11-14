"""Guard canonical primary-heading Guides in Kubernetes provider detail (#4645)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app/templates/integrations"
KUBERNETES = TEMPLATES / "orchestration/container_orchestrator/providers/kubernetes/partials"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_kubernetes_five_primary_headings_have_unique_canonical_guides() -> None:
    headings = {
        "_connection_contract.html": ("Connection Contract", "kubernetes-connection-contract-guide"),
        "_capsule_rbac_bootstrap.html": (
            "Capsule Cluster RBAC Bootstrap",
            "kubernetes-capsule-rbac-bootstrap-guide",
        ),
        "_capability_workspace.html": ("Kubernetes Full Validation", "kubernetes-full-validation-detail-guide"),
        "_runtime_workspace.html": ("Runtime Health & Diagnostics", "kubernetes-runtime-health-detail-guide"),
        "_inventory_lifecycle.html": ("Inventory &amp; Lifecycle", "kubernetes-inventory-lifecycle-detail-guide"),
    }
    for filename, (heading, guide_id) in headings.items():
        source = _source(KUBERNETES / filename)
        assert heading in source, filename
        assert source.count(f'"{guide_id}"') == 1, filename
        assert "info_tip.render(" in source, filename
        assert 'variant="guide"' in source, filename


def test_shared_provider_connection_contract_has_one_title_guide() -> None:
    source = _source(TEMPLATES / "components/_provider_configuration_contract.html")
    heading = '<h2 class="text-base font-semibold text-content-primary">Connection Contract</h2>'
    assert source.count(heading) == 1
    assert source.count("connection-contract-detail-guide") == 1
    assert source.index(heading) < source.index("connection-contract-detail-guide")
    assert 'variant="guide"' in source
