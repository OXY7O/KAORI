"""Contract for the committed Kubernetes Connection Registry source-binding label.

The registry displays normalized observability source bindings, not live
provider relationships. Keep the shared one-line label and accessible context.
"""

from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html"
)


def test_kubernetes_registry_uses_shared_single_line_binding_label():
    template = REGISTRY.read_text(encoding="utf-8")

    assert '{% import "components/table_label.html" as table_label %}' in template
    assert (
        "table_label.metadata_label(table_label.count_text(row.source_binding_count, 'Source'))"
        in template
    )
    assert "title=\"{{ table_label.count_text(row.source_binding_count, 'Consumer association') }}\"" in template

    # The old stacked caption must not return: the accessible title carries
    # the fuller meaning without adding another visible row.
    assert "<p>Consumer associations</p>" not in template
    assert "row.source_binding_count }}</p>" not in template
    assert "whitespace-nowrap" not in template.split(
        "table_label.metadata_label(table_label.count_text(row.source_binding_count, 'Source'))"
    )[0].split("<td")[-1]
