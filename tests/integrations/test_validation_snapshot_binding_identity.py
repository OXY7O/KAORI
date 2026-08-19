from app.integrations.validation.state import _binding_id_from_snapshot


def test_binding_id_prefers_explicit_snapshot_identity() -> None:
    assert _binding_id_from_snapshot({'binding_id': 7, 'scope_type': 'integration_binding', 'scope_key': 'binding:3'}) == 7


def test_binding_id_recovers_from_durable_job_scope() -> None:
    assert _binding_id_from_snapshot({'scope_type': 'integration_binding', 'scope_key': 'binding:3'}) == 3


def test_binding_id_does_not_infer_from_unrelated_scope() -> None:
    assert _binding_id_from_snapshot({'scope_type': 'integration_instance', 'scope_key': 'binding:3'}) is None
    assert _binding_id_from_snapshot({'scope_type': 'integration_binding', 'scope_key': 'cluster:3'}) is None
