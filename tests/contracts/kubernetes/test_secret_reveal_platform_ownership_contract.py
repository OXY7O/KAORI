from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_secret_reveal_administration_lives_under_platform_operations() -> None:
    old_python_domain = ROOT / 'app/settings/secret_reveal'
    old_template_domain = ROOT / 'app/templates/settings/secret_reveal'
    new_python_domain = ROOT / 'app/platform_operations/kubernetes/secret_reveal'
    new_template_domain = ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal'

    assert not old_python_domain.exists()
    assert not old_template_domain.exists()
    assert (new_python_domain / 'routes.py').exists()
    assert (new_python_domain / 'service.py').exists()
    assert (new_template_domain / 'index.html').exists()


def test_secret_reveal_routes_and_templates_have_no_legacy_settings_references() -> None:
    for root in (ROOT / 'app',):
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix not in {'.py', '.html', '.md'}:
                continue
            source = path.read_text(errors='ignore')
            assert 'settings.secret_reveal' not in source
            assert 'app/settings/secret_reveal' not in source
            assert 'app/templates/settings/secret_reveal' not in source
