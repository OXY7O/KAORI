from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "app/templates/components/info_flow.html"
ROLES = ROOT / "app/templates/settings/roles/index.html"
ALERTMANAGER = ROOT / "app/templates/alertmanager/instance_form.html"
STANDARD = ROOT / "docs/design/components/INFO_FLOW.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shared_info_flow_component_contract() -> None:
    source = read(COMPONENT)
    assert "macro render(" in source
    assert "<details" in source
    assert "<ol class=" in source
    assert "'%02d'|format(loop.index)" in source
    assert "rounded-full" in source
    assert "before:bg-outline-default" in source


def test_role_assignment_flow_uses_shared_component() -> None:
    source = read(ROLES)
    assert 'components/info_flow.html' in source
    assert "info_flow.render(" in source
    assert "'Role Assignment Flow'" in source
    assert "'Permission Catalog'" in source
    assert "'Role Composition'" in source
    assert "'User Management'" in source


def test_alertmanager_registration_flow_uses_shared_component() -> None:
    source = read(ALERTMANAGER)
    assert 'components/info_flow.html' in source
    assert "info_flow.render(" in source
    assert "'Alertmanager Registration Flow'" in source
    assert "'Register Connection Identity'" in source
    assert "'Verify Reachability'" in source
    assert "'Validate Capabilities'" in source
    assert "'Assign Operational Scope'" in source
    assert "Registration creates the reusable connection identity only" in source


def test_info_flow_standard_is_documented() -> None:
    source = read(STANDARD)
    assert "three to five" in source.lower()
    assert "Title Case" in source
    assert "Boundary note" in source
    assert "components/info_flow.html" in source
