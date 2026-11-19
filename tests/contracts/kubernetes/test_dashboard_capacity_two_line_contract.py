from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_dashboard_capacity_uses_value_then_description_two_line_contract() -> None:
    schema = read('app/kubernetes/dashboard/schema.py')
    section = read('app/kubernetes/dashboard/sections/capacity.py')
    template = read('app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html')

    assert "value: str = 'N/A'" in schema
    assert "value = f'{used:.{digits}f} / {capacity:.{digits}f}'" in section
    assert "description = f'worker allocatable {unit}'" in section
    assert "value = f'{int(round(used))} / {int(round(capacity))}'" in section
    assert "description = f'{unit} on worker nodes'" in section
    shared = read('app/templates/components/operational_capacity_metric_card.html')

    assert 'components/operational_capacity_metric_card.html' in template
    assert 'capacity_metric_card.render(item.label,' in template
    assert 'item.value,' in template
    assert 'item.description,' in template
    assert template.index('item.value,') < template.index('item.description,')
    assert '{{ value }}' in shared
    assert '{{ description }}' in shared
    assert shared.index('{{ value }}') < shared.index('{{ description }}')
    assert '% Headroom' not in template


def test_shared_capacity_metric_card_preserves_percentage_and_missing_evidence() -> None:
    from jinja2 import Environment, FileSystemLoader

    root = Path(__file__).resolve().parents[3]
    env = Environment(loader=FileSystemLoader(str(root / 'app/templates')), autoescape=True)
    render = env.get_template('components/operational_capacity_metric_card.html').module.render

    observed = render(
        'Used Capacity',
        '7.7 GiB',
        'Committed storage usage',
        0.8,
        'Used',
        'bg-kaori-primary',
    )
    missing = render(
        'Artifact Footprint',
        '898.0 GiB',
        'Committed inventory footprint',
        None,
        'Inventory',
        'bg-kaori-primary',
        missing_label='Inventory',
    )
    zero = render(
        'Public Quota',
        '0 GiB',
        'Observed zero',
        0,
        'Used',
        'bg-status-info',
    )

    assert '0.8% Used' in observed
    assert 'Committed storage usage' in observed
    assert 'role="progressbar"' in observed
    assert observed.index('7.7 GiB') < observed.index('Committed storage usage')
    assert 'Inventory' in missing
    assert 'percentage unavailable' in missing
    assert 'role="progressbar"' not in missing
    assert '0% Used' in zero
    assert 'role="progressbar"' in zero

    shared = read('app/templates/components/operational_capacity_metric_card.html')
    assert 'components/progress_bar.html' in shared
    assert 'percent is not none' in shared
    assert 'grid gap-3 lg:grid-cols-3' not in shared
    assert 'whitespace-nowrap' not in shared
    assert 'truncate' not in shared


def test_three_dashboard_capacity_sections_use_one_shared_card_presentation() -> None:
    paths = (
        'app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html',
        'app/templates/storage/object_storage/dashboard/partials/_capacity.html',
        'app/templates/artifact_registry/partials/_overview_capacity_snapshot.html',
    )
    for path in paths:
        source = read(path)
        assert 'components/operational_capacity_metric_card.html' in source
        assert 'capacity_metric_card.render(' in source
        assert 'grid gap-3 lg:grid-cols-3' in source
        assert 'components/operational_section_card.html' in source
        assert 'Data Scope:' in source

    kubernetes, storage, registry = (read(path) for path in paths)
    assert 'item.used_percent' in kubernetes
    assert "'Used'" in kubernetes
    assert 'digits=0' in kubernetes
    assert 'dashboard.capacity.utilization if dashboard.capacity.utilization is number else none' in storage
    assert "'Used Capacity'" in storage and "'Free Capacity'" in storage and "'Usable Capacity'" in storage
    assert 'overview.capacity.metrics' in registry
    assert "missing_label='Inventory' if item.progress_label == 'Inventory' else 'No Quota'" in registry
