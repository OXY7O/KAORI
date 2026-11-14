"""Guard canonical primary-heading Guides in Kubernetes provider detail (#4645)."""

import re
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
    heading = re.compile(r'<h2\s+id="[^"]+-connection-contract-title"\s+class="text-base font-semibold text-content-primary">Connection Contract</h2>')
    matches = list(heading.finditer(source))
    assert len(matches) == 1
    assert source.count("connection-contract-detail-guide") == 1
    assert matches[0].end() < source.index("connection-contract-detail-guide")
    assert 'variant="guide"' in source


def test_kubernetes_validation_and_runtime_guides_are_passed_to_primary_headers() -> None:
    """A Guide elsewhere in the template must not satisfy the title contract."""
    for filename, guide_id in (
        ("_capability_workspace.html", "kubernetes-full-validation-detail-guide"),
        ("_runtime_workspace.html", "kubernetes-runtime-health-detail-guide"),
    ):
        source = _source(KUBERNETES / filename)
        header_start = source.index("{% call connection_validation_header.render(")
        header_end = source.index("%}", header_start)
        header_call = source[header_start:header_end]
        assert "title_extra=info_tip.render(" in header_call, filename
        assert f'"{guide_id}"' in header_call, filename
        assert 'placement="right", variant="guide"' in header_call, filename


def test_shared_configuration_guide_is_adjacent_to_primary_heading() -> None:
    """Prevent a regression that moves the Guide into a footer or inner card."""
    source = _source(TEMPLATES / "components/_provider_configuration_contract.html")
    heading = re.compile(r'<h2\s+id="[^"]+-connection-contract-title"\s+class="text-base font-semibold text-content-primary">Connection Contract</h2>')
    title_row = source[source.index('<div class="flex flex-wrap items-center gap-2">'):]
    title_row = title_row[: title_row.index("</div>")]
    assert heading.search(title_row)
    assert title_row.count("info_tip.render(") == 1
    assert "connection-contract-detail-guide" in title_row
    assert source.count("aria-labelledby=") >= 1
    assert 'aria-labelledby="{{ provider_label|lower|replace(\' + "\' \'" + ', \'-\') }}-connection-contract-title"' in source
