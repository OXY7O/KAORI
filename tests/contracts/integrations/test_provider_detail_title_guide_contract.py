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
    heading = re.compile(
        r'<h2\s+id="[^"]+-connection-contract-title"\s+'
        r'class="text-base font-semibold text-content-primary">Connection Contract</h2>'
    )
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
    heading = re.compile(
        r'<h2\s+id="[^"]+-connection-contract-title"\s+'
        r'class="text-base font-semibold text-content-primary">Connection Contract</h2>'
    )
    title_row = source[source.index('<div class="flex flex-wrap items-center gap-2">'):]
    title_row = title_row[: title_row.index("</div>")]
    assert heading.search(title_row)
    assert title_row.count("info_tip.render(") == 1
    assert "connection-contract-detail-guide" in title_row
    assert source.count("aria-labelledby=") >= 1
    assert 'aria-labelledby="{{ provider_label|lower|replace(\' \', \'-\') }}-connection-contract-title"' in source


def test_shared_connection_guide_section_describes_its_scope_accessibly() -> None:
    """The primary Guide heading and visible helper jointly name the section."""
    source = _source(TEMPLATES / "components/_provider_configuration_contract.html")
    slug = "{{ provider_label|lower|replace(' ', '-') }}"
    assert f'aria-labelledby="{slug}-connection-contract-title"' in source
    assert f'aria-describedby="{slug}-connection-contract-description"' in source
    assert f'<p id="{slug}-connection-contract-description"' in source
    assert source.count("-connection-contract-description") == 2


def test_kubernetes_primary_heading_guide_ids_do_not_collide_across_tabs() -> None:
    """Distinct tab Guides must keep distinct popover controller IDs."""
    expected = {
        "_connection_contract.html": "kubernetes-connection-contract-guide",
        "_capsule_rbac_bootstrap.html": "kubernetes-capsule-rbac-bootstrap-guide",
        "_capability_workspace.html": "kubernetes-full-validation-detail-guide",
        "_runtime_workspace.html": "kubernetes-runtime-health-detail-guide",
        "_inventory_lifecycle.html": "kubernetes-inventory-lifecycle-detail-guide",
    }
    seen: set[str] = set()
    for filename, guide_id in expected.items():
        source = _source(KUBERNETES / filename)
        assert guide_id not in seen, filename
        assert source.count(f'"{guide_id}"') == 1, filename
        seen.add(guide_id)
    assert len(seen) == len(expected)


def test_kubernetes_connection_guide_section_has_matching_accessible_references() -> None:
    """The named section must point to its own visible title and scope copy."""
    source = _source(KUBERNETES / "_connection_contract.html")
    section = source.split('data-kaori-connection-contract-v2', 1)[1]
    section = section.split('<section aria-labelledby="connection-summary-title"', 1)[0]
    for suffix, tag in (("title", "h2"), ("description", "p")):
        target = f"kubernetes-connection-contract-{suffix}"
        attribute = "aria-labelledby" if suffix == "title" else "aria-describedby"
        assert section.count(f'{attribute}="{target}"') == 1
        assert section.count(f'<{tag} id="{target}"') == 1
    assert section.index('id="kubernetes-connection-contract-title"') < section.index(
        '"kubernetes-connection-contract-guide"'
    )


def test_capsule_rbac_guide_section_exposes_visible_scope_description() -> None:
    """Capsule RBAC section must resolve both its title and explanatory scope."""
    source = _source(KUBERNETES / "_capsule_rbac_bootstrap.html")
    section = source.split('data-capsule-rbac-bootstrap>', 1)[0]
    assert 'aria-labelledby="capsule-rbac-bootstrap-heading"' in section
    assert 'aria-describedby="capsule-rbac-bootstrap-description"' in section
    assert source.count('id="capsule-rbac-bootstrap-description"') == 1
    assert source.index('id="capsule-rbac-bootstrap-description"') > source.index(
        '"kubernetes-capsule-rbac-bootstrap-guide"'
    )
