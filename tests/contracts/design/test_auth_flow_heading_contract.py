"""Pre-session auth headings keep their existing semantics under one shared owner."""

import importlib.util
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates'
SHARED = 'components/auth_flow_heading.html'
CASES = (
    (
        'access/authentication/bot_challenge.html',
        'bot-challenge-title',
        'Verify Your Sign In',
        'standard',
    ),
    (
        'access/authentication/mfa_challenge.html',
        'mfa-challenge-title',
        'Verify Your Sign In',
        'challenge',
    ),
    (
        'access/authentication/mfa_enrollment.html',
        'mfa-enroll-title',
        'Authenticator Enrollment Required',
        'standard',
    ),
    (
        'access/authentication/mfa_recovery_codes.html',
        'mfa-recovery-title',
        'MFA Enabled — Save Recovery Codes',
        'standard',
    ),
)


def test_auth_flow_heading_preserves_accessible_identity_and_visual_classes() -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    shared = env.get_template(SHARED)
    heading = shared.module.title
    styles = {
        'standard': 'mt-4 text-xl font-semibold text-content-primary',
        'challenge': 'mt-2 text-2xl font-bold tracking-tight text-content-primary',
    }
    for path, heading_id, title, variant in CASES:
        page = (TEMPLATES / path).read_text(encoding='utf-8')
        env.parse(page)
        assert '{% import "components/auth_flow_heading.html" as auth_flow_heading %}' in page
        assert f"auth_flow_heading.title('{heading_id}', '{title}', '{variant}')" in page
        assert f'aria-labelledby="{heading_id}"' in page
        assert '<h1' not in page
        assert page.count('auth_flow_heading.title(') == 1

        rendered = str(heading(heading_id, title, variant))
        assert rendered.count('<h1') == 1
        assert f'id="{heading_id}"' in rendered
        assert f'class="{styles[variant]}"' in rendered
        assert f'>{title}</h1>' in rendered


def test_auth_flow_shared_authority_does_not_hide_page_local_style_debt() -> None:
    verifier = ROOT / 'scripts' / 'verify_ui_style.py'
    spec = importlib.util.spec_from_file_location('verify_ui_style', verifier)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    component = 'app/templates/components/auth_flow_heading.html'
    shared = (ROOT / component).read_text(encoding='utf-8')
    assert component in module._APPROVED_CUSTOM_HERO_COMPONENTS
    assert module._count_custom_hero_titles(component, shared) == 0
    for path, _, _, _ in CASES:
        relative = f'app/templates/{path}'
        assert module._count_custom_hero_titles(relative, '<h1>Unauthorized title</h1>') == 1

    guide = (ROOT / 'docs/design/KAORI_STYLING_GUIDE.md').read_text(encoding='utf-8')
    assert 'Pre-Session Authentication Flow Heading' in guide
    assert 'page-local unmarked H1 tags are **still style debt**' in guide
