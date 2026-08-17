from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_pod_detail_uses_adaptive_natural_height_cards() -> None:
    template = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')

    assert "detail.detail_card('Pod Identity'" in template
    assert "detail.detail_card('Runtime & Conditions'" in template
    assert "detail.detail_card('Placement & Network'" in template
    assert "detail.detail_card('Pod Specification'" in template
    assert 'stretch=false' in template
    assert "density='compact'" in template
    assert 'xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in template
    assert 'min-h-96' not in template
    assert 'min-h-[32rem]' not in template
    assert 'min-h-[30rem]' not in template


def test_pod_configuration_is_factual_without_implicit_scoring() -> None:
    template = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')

    assert 'pod.specification_rows' in template
    assert 'explicit governance policy' in template
    assert "'besteffort': 'warning'" not in template
    assert "'never': 'warning'" not in template
    assert "'none': 'warning'" not in template
    assert 'normalized_selector' not in template


def test_runtime_and_volume_types_use_shared_component_owners() -> None:
    detail_template = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')
    runtime_component = read('app/templates/components/container_runtime_collection.html')

    assert 'container_collection.render(pod.container_statuses)' in detail_template
    assert 'table_label.metadata_label(container.kind)' in runtime_component
    assert 'table_label.status_indicator_label(container.runtime_state_label' in runtime_component
    assert 'table_label.metadata_label(volume.type)' in detail_template
    assert 'technical_value.render(volume.source' in detail_template
