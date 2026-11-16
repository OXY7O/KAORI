"""Bounded remote Linux facts evidence projection for #4799.

Pure validation only: no SSH, credential resolution, worker dispatch or approval.
Only an independently admitted worker may supply observations to this contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
_OS = frozenset({"Ubuntu", "OracleLinux"})
_FACT_KEYS = frozenset({"distribution", "version", "kernel", "architecture", "cpu_count", "memory_mib"})


@dataclass(frozen=True, slots=True)
class RemoteFactsProjection:
    status: str
    findings: tuple[str, ...]
    facts: dict[str, str | int] | None
    mutation_authorized: bool = False


def project_remote_facts(
    *,
    observed: object,
    expected_asset_id: str,
    expected_source_sha: str,
    expected_ee_digest: str,
    expected_host_key_fingerprint: str,
) -> RemoteFactsProjection:
    """Reject untrusted/malformed observations without persisting raw payloads.

    The expected identifiers MUST be resolved independently from canonical
    asset, source, signed EE and SSH host-key authorities by a future worker.
    Caller-supplied expected values alone do not establish that trust.
    """
    denied = RemoteFactsProjection("blocked", ("REMOTE_FACTS_UNQUALIFIED",), None)
    if (
        not isinstance(expected_asset_id, str)
        or not expected_asset_id
        or expected_asset_id != expected_asset_id.strip()
        or len(expected_asset_id) > 96
        or not isinstance(expected_source_sha, str)
        or not _SHA.fullmatch(expected_source_sha)
        or not isinstance(expected_ee_digest, str)
        or not _DIGEST.fullmatch(expected_ee_digest)
        or not isinstance(expected_host_key_fingerprint, str)
        or not _FINGERPRINT.fullmatch(expected_host_key_fingerprint)
        or not isinstance(observed, Mapping)
    ):
        return denied
    if set(observed) != {
        "asset_id", "source_sha", "ee_digest", "host_key_fingerprint",
        "operation", "runner_status", "runner_rc", "changed", "facts",
    }:
        return denied
    if (
        observed["asset_id"] != expected_asset_id
        or observed["source_sha"] != expected_source_sha
        or observed["ee_digest"] != expected_ee_digest
        or observed["host_key_fingerprint"] != expected_host_key_fingerprint
        or observed["operation"] != "linux.host_facts.v1"
        or observed["runner_status"] != "successful"
        or type(observed["runner_rc"]) is not int
        or observed["runner_rc"] != 0
        or observed["changed"] is not False
    ):
        return denied
    facts = observed["facts"]
    if not isinstance(facts, Mapping) or set(facts) != _FACT_KEYS:
        return denied
    distribution = facts["distribution"]
    version = facts["version"]
    kernel = facts["kernel"]
    architecture = facts["architecture"]
    cpu = facts["cpu_count"]
    memory = facts["memory_mib"]
    if (
        not isinstance(distribution, str)
        or distribution not in _OS
        or not isinstance(version, str)
        or not re.fullmatch(r"[0-9]{1,2}(?:\.[0-9]{1,2}){0,2}", version)
        or not isinstance(kernel, str)
        or not re.fullmatch(r"[A-Za-z0-9._+\-]{1,96}", kernel)
        or not isinstance(architecture, str)
        or architecture not in {"x86_64", "aarch64"}
        or type(cpu) is not int
        or not 1 <= cpu <= 4096
        or type(memory) is not int
        or not 128 <= memory <= 16777216
    ):
        return denied
    return RemoteFactsProjection(
        "requires_independent_admission",
        (),
        {
            "distribution": distribution,
            "version": version,
            "kernel": kernel,
            "architecture": architecture,
            "cpu_count": cpu,
            "memory_mib": memory,
        },
    )
