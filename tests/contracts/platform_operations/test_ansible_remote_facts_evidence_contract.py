"""Negative and positive evidence-contract tests for #4799."""

from app.infrastructure_automation.remote_facts_evidence import project_remote_facts

SHA = "a" * 40
EE = "sha256:" + "b" * 64
HOST_KEY = "SHA256:" + "A" * 43


def candidate():
    return {
        "asset_id": "asset-01",
        "source_sha": SHA,
        "ee_digest": EE,
        "host_key_fingerprint": HOST_KEY,
        "operation": "linux.host_facts.v1",
        "runner_status": "successful",
        "runner_rc": 0,
        "changed": False,
        "facts": {
            "distribution": "Ubuntu",
            "version": "24.04",
            "kernel": "6.8.0-40-generic",
            "architecture": "x86_64",
            "cpu_count": 4,
            "memory_mib": 8192,
        },
    }


def project(observed, **overrides):
    expected = {
        "expected_asset_id": "asset-01",
        "expected_source_sha": SHA,
        "expected_ee_digest": EE,
        "expected_host_key_fingerprint": HOST_KEY,
    }
    expected.update(overrides)
    return project_remote_facts(observed=observed, **expected)


def test_bounded_observation_never_authorizes_execution():
    result = project(candidate())
    assert result.status == "requires_independent_admission"
    assert result.mutation_authorized is False
    assert result.facts == candidate()["facts"]


def test_identity_source_ee_and_host_key_mismatch_fail_closed():
    for key, value in (
        ("asset_id", "asset-02"),
        ("source_sha", "c" * 40),
        ("ee_digest", "sha256:" + "c" * 64),
        ("host_key_fingerprint", "SHA256:" + "B" * 43),
    ):
        observation = candidate()
        observation[key] = value
        assert project(observation).status == "blocked"


def test_failed_changed_or_forged_runner_evidence_is_denied():
    for key, value in (
        ("runner_status", "failed"),
        ("runner_rc", True),
        ("runner_rc", 1),
        ("changed", 0),
        ("changed", True),
        ("operation", "shell.command"),
    ):
        observation = candidate()
        observation[key] = value
        assert project(observation).facts is None


def test_secret_bearing_extra_fields_and_unbounded_facts_are_denied():
    for key, value in (
        ("private_key", "secret"),
        ("events", [{"stdout": "password"}]),
        ("hostvars", {"ansible_password": "secret"}),
    ):
        observation = candidate()
        observation[key] = value
        assert project(observation).findings == ("REMOTE_FACTS_UNQUALIFIED",)
    observation = candidate()
    observation["facts"]["ansible_env"] = {"TOKEN": "secret"}
    assert project(observation).facts is None


def test_malformed_facts_and_authority_are_denied():
    for key, value in (
        ("cpu_count", True),
        ("memory_mib", -1),
        ("kernel", "6.8\npassword=secret"),
        ("distribution", "Other"),
        ("architecture", "unknown"),
    ):
        observation = candidate()
        observation["facts"][key] = value
        assert project(observation).status == "blocked"
    assert project(candidate(), expected_source_sha="main").status == "blocked"
    assert project(candidate(), expected_ee_digest="sha256:latest").status == "blocked"
    assert project(candidate(), expected_host_key_fingerprint="SHA256:short").status == "blocked"


def test_missing_or_unknown_evidence_never_claims_readiness():
    assert project(None).status == "blocked"
    assert project({}).status == "blocked"
    assert project(candidate() | {"approved": True}).status == "blocked"
