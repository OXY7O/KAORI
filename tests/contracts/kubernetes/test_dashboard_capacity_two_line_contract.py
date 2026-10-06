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
    assert '{{ item.value }}' in template
    assert '{{ item.description }}' in template
    assert template.index('{{ item.value }}') < template.index('{{ item.description }}')
    assert '% Headroom' not in template
