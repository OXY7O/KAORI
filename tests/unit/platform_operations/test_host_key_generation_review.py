"""Regression contracts for #4799 host-key rotation and stale evidence."""

from app.platform_operations.host_key_generation_review import review_host_key_generation


def _record():
    return {
        "asset_id": "asset-123",
        "inventory_fingerprint": "inventory-sha256",
        "host_key_ref": "known-hosts/asset-123",
        "host_key_generation": "generation-4",
        "host_key_fingerprint": "SHA256:canonical-value",
        "revoked": False,
    }


def test_exact_current_reference_is_only_review_candidate():
    assert review_host_key_generation(_record(), _record()) == "requires_independent_admission"


def test_rotation_invalidates_old_evidence():
    old = _record()
    current = _record()
    current["host_key_generation"] = "generation-5"
    assert review_host_key_generation(old, current) == "blocked"


def test_identity_drift_and_reference_change_fail_closed():
    for field in ("asset_id", "inventory_fingerprint", "host_key_ref", "host_key_fingerprint"):
        observed = _record()
        observed[field] += "-changed"
        assert review_host_key_generation(_record(), observed) == "blocked"


def test_revocation_or_non_boolean_flag_never_admits():
    for flag in (True, 1, "false", None):
        observed = _record()
        observed["revoked"] = flag
        assert review_host_key_generation(_record(), observed) == "blocked"


def test_missing_extra_or_secret_bearing_fields_fail_closed():
    for field in ("host_key_generation", "host_key_ref"):
        observed = _record()
        del observed[field]
        assert review_host_key_generation(_record(), observed) == "blocked"
    observed = _record()
    observed["private_key"] = "secret"
    assert review_host_key_generation(_record(), observed) == "blocked"


def test_malformed_identity_values_fail_closed():
    for value in ("", " space", "newline\n", "a" * 257, 123, None):
        observed = _record()
        observed["asset_id"] = value
        assert review_host_key_generation(_record(), observed) == "blocked"
