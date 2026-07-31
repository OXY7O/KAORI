from pathlib import Path


OPERATION_TEMPLATES = (
    'app/templates/kubernetes_operations/configmaps/create.html',
    'app/templates/kubernetes_operations/configmaps/update.html',
    'app/templates/kubernetes_operations/configmaps/delete.html',
    'app/templates/kubernetes_operations/secrets/create.html',
    'app/templates/kubernetes_operations/secrets/replace.html',
    'app/templates/kubernetes_operations/secrets/delete.html',
)


def test_shared_guidance_shell_supports_chevron_only_compact_action():
    shell = Path('app/templates/components/view_more_content.html').read_text()
    guide = Path('app/templates/components/information_guide_card.html').read_text()

    assert 'compact_action=false' in shell
    assert 'grid-cols-[auto_minmax(0,1fr)_auto]' in shell
    assert '{% if not compact_action %}' in shell
    assert 'sr-only group-open:hidden' in shell
    assert 'compact_action=compact_action' in guide


def test_secret_and_configmap_operation_rails_use_compact_action():
    for template_path in OPERATION_TEMPLATES:
        template = Path(template_path).read_text()
        assert 'compact_action=true' in template, template_path
