"""Source contracts for concise Alertmanager registration guidance (#4698)."""

import re
from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html"
)


def test_registration_guidance_preserves_connection_lifecycle() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "'Endpoint & Access'," in source
    assert "'Configure endpoint access, then test connectivity.'" in source
    assert 'flow_note="Registration creates identity; Full Validation gates consumer use."' in source
    assert 'alertmanager_related_description = "One Alertmanager serves multiple integrations."' in source
    assert "'Disabled connections stay stored but cannot serve consumers.'" in source


def test_registration_guidance_keeps_shared_components_and_binding_context() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "connection_validation_header.render(" in source
    assert "operational_toggle.render(" in source
    assert "provider_registration_context.render(" in source
    assert "if initial_cluster" in source
    assert "initial alert binding for " in source
    assert 'name="enabled"' in source
    assert 'name="verify_ssl"' in source
    assert "Run Full Validation" in source


def test_registration_guidance_remains_compact_without_forced_truncation() -> None:
    """Keep the four operator-reviewed helpers naturally readable on desktop."""
    source = TEMPLATE.read_text(encoding="utf-8")
    patterns = (
        r"'Endpoint & Access',\s*'([^']+)'",
        r'flow_note="(Registration[^"]+)"',
        r'alertmanager_related_description = "([^"]+)"',
        r"'Allow KAORI to Use This Connection',\s*'([^']+)'",
    )
    for pattern in patterns:
        match = re.search(pattern, source)
        assert match is not None, f"Missing registration helper: {pattern}"
        assert len(match.group(1)) <= 80, f"Registration helper is too verbose: {match.group(1)}"
        assert "\n" not in match.group(1)
        assert "\r" not in match.group(1)
        assert not re.search(r"\b(?:whitespace-nowrap|truncate|line-clamp-\d+)\b", match.group(1))


def test_registration_and_edit_flows_keep_distinct_validation_guidance() -> None:
    """A generic flow_note match must not silently test the edit flow instead."""
    source = TEMPLATE.read_text(encoding="utf-8")
    notes = re.findall(r'flow_note="([^"]+)"', source)

    assert len(notes) == 2, "Expected separate edit and registration guidance"
    assert notes[0] == "Saved changes require successful Full Validation."
    assert notes[1] == "Registration creates identity; Full Validation gates consumer use."
    assert all(len(note) <= 80 and "\n" not in note and "\r" not in note for note in notes)


def test_registration_guidance_does_not_introduce_forced_truncation_classes() -> None:
    """Reject template-level truncation, not just truncation words inside helper copy."""
    source = TEMPLATE.read_text(encoding="utf-8")
    assert not re.search(r"(?<![\w-])(?:whitespace-nowrap|text-ellipsis|truncate|line-clamp-\d+)(?![\w-])", source)


def test_registration_copy_does_not_weaken_connection_test_proof() -> None:
    """Concise helper copy must not bypass the existing proof invalidation flow."""
    source = TEMPLATE.read_text(encoding="utf-8")

    assert 'name="connection_test_proof"' in source
    assert 'x-ref="connectionProof"' in source
    assert 'x-on:input.capture="invalidateConnectionTest($event)"' in source
    assert 'x-on:change.capture="invalidateConnectionTest($event)"' in source
    assert 'x-on:alertmanager-connection-tested.window="applyConnectionTest($event)"' in source
    assert 'this.connectionVerified = false' in source
    assert "this.$refs.connectionProof.value = ''" in source
    assert 'hx-include="#alertmanager-instance-form"' in source
    assert 'hx-target="#alertmanager-connection-test-result"' in source
    # Only non-configuration bookkeeping fields may retain a valid proof.
    assert "['csrf_token', 'connection_test_proof'].includes(fieldName)" in source
    assert "const fieldName = event.target?.name || ''" in source
    assert "this.connectionVerified = event.detail?.connected === true" in source
    assert "this.$refs.connectionProof.value = event.detail?.proof || ''" in source
