from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_rejected_form_rerenders_existing_modal_with_operator_input() -> None:
    routes = (ROOT / 'app/reports/report_templates/routes.py').read_text()
    page = (ROOT / 'app/templates/reports/report_templates/index.html').read_text()
    assert 'def _render_invalid_template_form(' in routes
    assert 'get_template_form_state(request.form)' in routes
    assert "payload['edit_template'] = submitted" in routes
    assert "payload['create_form'] = submitted" in routes
    assert "render_template('reports/report_templates/index.html', payload=payload), 422" in routes
    assert "payload.get('form_errors')" in page
    assert 'data-template-server-validation' in page
    assert 'role="alert"' in page
    assert 'data-template-open-form-dialog=' in page


def test_registry_context_remains_same_origin_and_scoped() -> None:
    routes = (ROOT / 'app/reports/report_templates/routes.py').read_text()
    assert 'safe_next_url(value)' in routes
    assert 'MultiDict(parse_qsl(urlsplit(registry_return_url).query, keep_blank_values=True))' in routes
    assert "registry_return_url = _template_registry_return_url(request.form.get('next'))" in routes
