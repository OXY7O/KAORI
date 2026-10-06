from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_reviewed_dast_warning_dispositions_are_documented() -> None:
    dispositions = read('docs/security/DAST_WARNING_DISPOSITIONS.md')

    for alert_id in ('10031', '10049', '10055', '10109', '10111', '10112', '90004'):
        assert alert_id in dispositions

    assert 'FAIL-NEW' in dispositions
    assert 'tests/security/test_http_response_security.py' in dispositions
    assert '@alpinejs/csp' in dispositions


def test_response_security_adds_site_isolation_without_weakening_nonce_csp() -> None:
    security = read('app/bootstrap/security.py')

    assert '"script-src-attr \'none\'"' in security
    assert "response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'" in security
    assert "response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'" in security
    assert "response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'" in security
    assert "'unsafe-inline'" not in security.split('script-src', 1)[1].split('style-src', 1)[0]


def test_zap_fail_new_gate_remains_authoritative() -> None:
    baseline = read('.github/ci/run-zap-baseline.sh')

    assert 'zap-baseline.py' in baseline
    assert 'baseline.json' in baseline
    assert '  -I \\' in baseline
    assert 'PASS — KAORI ZAP Baseline' in baseline


def test_corp_is_global_while_document_isolation_remains_html_only() -> None:
    security = read('app/bootstrap/security.py')
    before_html, html_branch = security.split("        if response.mimetype == 'text/html':", 1)

    assert "response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'" in before_html
    assert "response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'" not in before_html
    assert "response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'" not in before_html
    assert "response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'" in html_branch
    assert "response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'" in html_branch
