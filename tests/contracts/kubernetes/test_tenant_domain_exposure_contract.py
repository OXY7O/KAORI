from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_domain_and_exposure_policy_persistence_is_canonical() -> None:
    model = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_domain_exposure.py').read_text(encoding='utf-8')

    assert 'class TenantDomainReservation(db.Model):' in model
    assert 'class TenantExposurePolicy(db.Model):' in model
    assert "EXACT = 'exact'" in model
    assert "WILDCARD = 'wildcard'" in model
    assert "REGEX = 'regex'" in model
    assert 'allow_node_port' in model
    assert 'allow_load_balancer' in model
    assert 'allow_external_name' in model
    assert "down_revision = '20260926_tenant_managed_res'" in migration


def test_policy_service_records_reservation_and_preflight_evidence() -> None:
    service = (ROOT / 'app/kubernetes/tenant/domain_exposure_service.py').read_text(encoding='utf-8')

    assert 'def create_domain_reservation_committed(' in service
    assert 'def create_exposure_policy_committed(' in service
    assert 'def record_service_exposure_preflight_committed(' in service
    assert 'def record_ingress_preflight_committed(' in service
    assert "target_type = 'tenant_policy'" in service


def test_default_profile_is_ingress_only() -> None:
    service = (ROOT / 'app/kubernetes/tenant/domain_exposure_service.py').read_text(encoding='utf-8')

    assert "profile_key = 'ingress_only'" in service
    assert 'allow_cluster_ip = True' in service
    assert 'allow_ingress = True' in service
    assert 'allow_node_port = False' in service
    assert 'allow_load_balancer = False' in service
    assert 'allow_external_name = False' in service


def test_architecture_keeps_policy_separate_from_rbac() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-domain-exposure.md').read_text(encoding='utf-8')

    assert 'separate from RBAC' in docs
    assert 'Exact' in docs
    assert 'NodePort' in docs
    assert 'LoadBalancer' in docs
    assert 'ExternalName' in docs
