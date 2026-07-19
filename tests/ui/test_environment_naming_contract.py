from pathlib import Path

from app.cluster.constants import get_environment_label, normalize_environment_value


def test_environment_aliases_render_as_full_names():
    assert get_environment_label('dev') == 'Development'
    assert get_environment_label('stg') == 'Staging'
    assert get_environment_label('prod') == 'Production'
    assert get_environment_label('qa') == 'Quality Assurance'
    assert get_environment_label('uat') == 'User Acceptance Testing'
    assert get_environment_label('dr') == 'Disaster Recovery'
    assert get_environment_label('poc') == 'Proof of Concept'


def test_environment_aliases_normalize_to_canonical_values():
    assert normalize_environment_value('prd') == 'production'
    assert normalize_environment_value('stage') == 'staging'
    assert normalize_environment_value('pre-prod') == 'pre_production'


def test_active_templates_do_not_render_abbreviated_environment_names():
    root = Path('app/templates')
    forbidden = ('>DEV<', '>STG<', '>PROD<', '>PRD<', '>QA<', '>UAT<')
    for path in root.rglob('*.html'):
        content = path.read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in content, f'{path} renders forbidden environment abbreviation {token}'

def test_environment_display_uses_shared_filter_in_known_dynamic_views():
    required = {
        'app/templates/integrations/kubernetes/detail.html',
        'app/templates/integrations/prometheus/partials/_instance_inventory.html',
        'app/templates/inventory/overview/partials/_resources_by_cluster_content.html',
    }
    for filename in required:
        assert '|environment_name' in Path(filename).read_text(encoding='utf-8')
