from pathlib import Path


def test_configmap_create_guardrails_use_chevron_only_compact_action():
    template = Path('app/templates/kubernetes_operations/configmaps/create.html').read_text()
    assert 'compact_action=true' in template


def test_shared_guidance_components_support_compact_action():
    view_more = Path('app/templates/components/view_more_content.html').read_text()
    guide = Path('app/templates/components/information_guide_card.html').read_text()
    assert 'compact_action=false' in view_more
    assert '{% if not compact_action %}' in view_more
    assert 'compact_action=compact_action' in guide
