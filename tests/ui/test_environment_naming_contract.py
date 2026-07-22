from pathlib import Path

from app.cluster.constants import ENVIRONMENTS, get_environment_label, normalize_environment_value


def test_environment_choices_store_full_canonical_values() -> None:
    values = {value for value, _label in ENVIRONMENTS}
    assert {'development', 'staging', 'production'} <= values
    assert not {'dev', 'stg', 'prd', 'prod'} & values


def test_environment_normalization_preserves_canonical_values() -> None:
    assert normalize_environment_value('production') == 'production'
    assert normalize_environment_value('quality-assurance') == 'quality_assurance'
    assert normalize_environment_value('pre production') == 'pre_production'
    assert get_environment_label('quality_assurance') == 'Quality Assurance'


def test_active_templates_do_not_render_abbreviated_environment_names() -> None:
    root = Path('app/templates')
    forbidden = ('>DEV<', '>STG<', '>PROD<', '>PRD<', '>QA<', '>UAT<')
    for path in root.rglob('*.html'):
        content = path.read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in content, f'{path} renders forbidden environment abbreviation {token}'


def test_environment_display_uses_shared_filter_in_known_dynamic_views() -> None:
    required = {
        'app/templates/integrations/kubernetes/detail.html',
        'app/templates/integrations/prometheus/partials/_instance_inventory.html',
        'app/templates/inventory/overview/partials/_resources_by_cluster_content.html',
    }
    for filename in required:
        assert '|environment_name' in Path(filename).read_text(encoding='utf-8')
