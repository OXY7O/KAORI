from __future__ import annotations

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest

from app.platform_operations.data_lifecycle.routes import _mutation_domain


@pytest.mark.parametrize('invalid_domain', [None, '', 'unknown_adapter', '  '])
def test_mutation_domain_rejects_missing_or_unsupported_domain(invalid_domain: str | None) -> None:
    app = Flask(__name__)
    form = {} if invalid_domain is None else {'domain': invalid_domain}
    with app.test_request_context('/platform-operations/data-lifecycle/policy', method='POST', data=form):
        with pytest.raises(BadRequest):
            _mutation_domain()


@pytest.mark.parametrize('valid_domain', ['operational_activity', 'job_execution', 'tenant_audit_evidence'])
def test_mutation_domain_accepts_registered_domains(valid_domain: str) -> None:
    app = Flask(__name__)
    with app.test_request_context('/platform-operations/data-lifecycle/run', method='POST', data={'domain': valid_domain}):
        assert _mutation_domain() == valid_domain


def test_mutating_routes_do_not_call_read_only_domain_fallback() -> None:
    from pathlib import Path

    routes = Path('app/platform_operations/data_lifecycle/routes.py').read_text(encoding='utf-8')
    assert routes.count('domain_name=_mutation_domain(),') == 2
    assert 'domain_name=_domain(),' not in routes
