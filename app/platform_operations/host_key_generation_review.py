"""Review-only SSH host-key generation coherence for Kubespray #4799.

This checks equality of already independently issued references. It does not
authenticate an issuer, fetch known_hosts, or authorize a remote operation.
"""

from collections.abc import Mapping

_FIELDS = frozenset({
    "asset_id", "inventory_fingerprint", "host_key_ref",
    "host_key_generation", "host_key_fingerprint",
})


def review_host_key_generation(
    expected: Mapping[str, object], observed: Mapping[str, object]
) -> str:
    """Fail closed on rotated, revoked, malformed or mismatched key evidence."""
    for record in (expected, observed):
        # Only canonical decoded JSON objects are admissible. Arbitrary Mapping
        # implementations can execute code or raise during iteration/lookup,
        # and must never be trusted as authority evidence.
        if type(record) is not dict or record.keys() != _FIELDS | {"revoked"}:
            return "blocked"
        if type(record["revoked"]) is not bool or record["revoked"]:
            return "blocked"
        for field in _FIELDS:
            value = record[field]
            if type(value) is not str or not value or value != value.strip():
                return "blocked"
            if len(value) > 256 or any(ord(char) < 33 or ord(char) == 127 for char in value):
                return "blocked"
    if any(expected[field] != observed[field] for field in _FIELDS):
        return "blocked"
    return "requires_independent_admission"
