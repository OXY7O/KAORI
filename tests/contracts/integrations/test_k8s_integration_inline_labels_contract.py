from pathlib import Path

def test_table_label_uses_nowrap_for_semantic_labels():
    content = Path('app/templates/components/table_label.html').read_text()
    assert 'whitespace-nowrap' in content


def test_inventory_lifecycle_status_labels_are_shrink_safe():
    content = Path('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html').read_text()
    assert 'Guardrails Passed' in content
    assert 'Committed Snapshot' in content or 'inventory_status_label' in content
    assert 'shrink-0' in content
