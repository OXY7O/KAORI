"""Negative contracts for the inert #4799 remote facts command specification."""
import pytest

from app.infrastructure_automation.remote_facts_command import (
    RemoteFactsCommandDenied,
    build_remote_facts_command,
)


def test_fixed_setup_only_specification():
    command = build_remote_facts_command(inventory_host="worker-01.example.internal")
    assert command.module == "ansible.builtin.setup"
    assert command.limit == "worker-01.example.internal"
    assert command.forks == 1
    assert command.timeout == 30
    assert command.become is False
    assert command.check is True
    assert "network,hardware" in command.module_args


@pytest.mark.parametrize(
    "host",
    [
        None, 123, True, "", "localhost", "127.0.0.1", ".", "..",
        "../etc/passwd", "worker;id", "worker && whoami", "worker\nother",
        "worker other", "--limit=all", "worker..internal", "éxample",
        "x" * 254,
    ],
)
def test_rejects_unsafe_inventory_keys(host):
    with pytest.raises(RemoteFactsCommandDenied):
        build_remote_facts_command(inventory_host=host)


def test_no_caller_override_of_module_or_privilege():
    with pytest.raises(TypeError):
        build_remote_facts_command(inventory_host="worker-01", module="shell")
    with pytest.raises(TypeError):
        build_remote_facts_command(inventory_host="worker-01", become=True)


def test_specification_is_immutable():
    command = build_remote_facts_command(inventory_host="worker-01")
    with pytest.raises(AttributeError):
        command.module = "ansible.builtin.shell"
