from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_replacement_route_uses_the_service_dry_run_contract() -> None:
    route = read('app/kubernetes_operations/secrets/routes.py')
    service = read('app/kubernetes_operations/secrets/replace_service.py')

    assert 'def execute_secret_replacement(' in service
    assert 'dry_run: bool' in service
    assert 'execute_secret_replacement(request.form, request.files, dry_run=True)' in route
    assert 'execute_secret_replacement(request.form, request.files, dry_run=False)' in route
    assert 'execute_secret_replacement(request.form, request.files, validate_only=' not in route


def test_tls_inventory_checks_schema_before_querying_the_evolving_model() -> None:
    readiness = read('app/governance/tls_certificates/readiness.py')
    service = read('app/governance/tls_certificates/service.py')
    migration = read('migrations/versions/20260731_tls_governance_evidence.py')

    for column in ('coverage_state', 'declared_host_count', 'covered_host_count', 'uncovered_hosts'):
        assert column in readiness
        assert column in migration
    assert "TLS_EVIDENCE_REVISION = '20260731_tls_evidence'" in readiness
    assert 'inspect(db.engine)' in readiness
    assert 'check_tls_governance_schema_readiness()' in service
    assert 'return _schema_blocked_payload(args, schema_readiness)' in service


def test_tls_rotation_renders_an_operator_blocker_instead_of_a_500() -> None:
    route = read('app/kubernetes_operations/secrets/routes.py')
    governance_route = read('app/governance/tls_certificates/routes.py')
    page = read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    blocker = read('app/templates/governance/tls_certificates/partials/_schema_blocker.html')

    assert "if not payload['schema_readiness']['ready']" in route
    assert 'check_tls_governance_schema_readiness()' in governance_route
    assert 'if not schema_readiness.ready' in governance_route
    assert 'if not payload.schema_readiness.ready' in page
    assert 'data-kaori-tls-schema-blocker' in blocker
    assert '20260731_tls_evidence' not in blocker
    assert 'readiness.required_revision' in blocker
    assert 'flask --app run:app db upgrade' in blocker
    assert 'docker compose -f compose.production.yml run --rm migrate' in blocker
    assert route.count("'kubernetes_operations/secrets/tls_rotation.html',\n        'kubernetes_operations/secrets/tls_rotation.html'") == 0
