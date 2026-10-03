from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_artifact_registry_workspace_exposes_complete_review_surface() -> None:
    navigation = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    for capability in (
        "'artifact_registry.overview'",
        "'artifact_registry.inventory'",
        "'artifact_registry.security'",
        "'artifact_registry.runtime'",
        "'artifact_registry.governance'",
        "'artifact_registry.analytics'",
    ):
        assert capability in navigation
    for route in (
        "def overview()",
        "def inventory()",
        "def security()",
        "def runtime()",
        "def governance()",
        "def analytics()",
    ):
        assert route in routes
