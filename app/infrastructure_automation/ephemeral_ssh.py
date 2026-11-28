"""Candidate worker-only SSH material preparation (#5186/#5204).

No provider read, socket, SSH invocation, job dispatch or runtime permit.
Only a future independently admitted isolated worker may use this context.
"""

from __future__ import annotations

import os
import re
import shlex
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.infrastructure_automation.remote_preflight_source import REMOTE_GROUP
from app.infrastructure_automation.ssh_host_key import qualify_ed25519_host_key
from app.integrations.secrets_management.secrets_pki.providers.ssh_credential_material import SSHCredentialMaterial

_ALIAS = re.compile(r'kaori-[1-9][0-9]{0,18}')
_USERNAME = re.compile(r'[a-z_][a-z0-9_-]{0,30}')
_PRIVATE = tuple(IPv4Network(cidr) for cidr in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


class EphemeralSSHError(ValueError):
    """Sanitized worker preparation failure."""


@dataclass(frozen=True, slots=True, repr=False)
class SSHMaterialTarget:
    """Internal exact endpoint from canonical assignment and current console trust."""

    alias: str
    address: str
    port: int
    host_key: str
    host_key_digest: str
    credential: SSHCredentialMaterial = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class EphemeralSSHFiles:
    """Transient file paths, never committed or returned in a job summary."""

    config: Path
    known_hosts: Path
    inventory: Path
    execution_authorized: bool = False

    @property
    def ssh_args(self) -> str:
        """Explicit candidate SSH args; override Runner defaults, not append to them."""
        return shlex.join((
            '-F', str(self.config),
            '-o', 'ControlMaster=no',
            '-o', 'ControlPath=none',
            '-o', 'ControlPersist=no',
        ))


def _deny() -> EphemeralSSHError:
    return EphemeralSSHError('Ephemeral SSH preparation is unavailable or unqualified.')


def _worker_tmpfs_root() -> Path:
    """Require the fixed Linux tmpfs mount and a non-root process; no disk fallback."""
    root = Path('/dev/shm')
    if os.geteuid() == 0 or root.is_symlink():
        raise _deny()
    try:
        info = root.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or not info.st_mode & stat.S_ISVTX:
            raise _deny()
        matches = []
        with Path('/proc/self/mountinfo').open(encoding='utf-8') as stream:
            for line in stream:
                left, sep, right = line.partition(' - ')
                fields = left.split()
                if sep and len(fields) >= 6 and fields[4] == str(root):
                    matches.append(right.split()[0])
        if matches != ['tmpfs'] or not os.path.ismount(root):
            raise _deny()
    except (OSError, ValueError, IndexError):
        raise _deny() from None
    return root


def _validate_targets(targets: tuple[SSHMaterialTarget, ...]) -> None:
    if type(targets) is not tuple or len(targets) != 3:
        raise _deny()
    aliases: set[str] = set()
    endpoints: set[str] = set()
    for target in targets:
        if type(target) is not SSHMaterialTarget:
            raise _deny()
        if (
            not isinstance(target.alias, str)
            or _ALIAS.fullmatch(target.alias) is None
            or target.alias in aliases
            or not isinstance(target.address, str)
            or type(target.port) is not int
            or not 1 <= target.port <= 65535
            or not isinstance(target.credential, SSHCredentialMaterial)
            or not isinstance(target.credential.private_key, Ed25519PrivateKey)
            or not isinstance(target.credential.username, str)
            or _USERNAME.fullmatch(target.credential.username) is None
            or target.credential.username == 'root'
        ):
            raise _deny()
        try:
            ip = IPv4Address(target.address)
        except ValueError:
            raise _deny() from None
        if str(ip) != target.address or not any(ip in network for network in _PRIVATE) or target.address in endpoints:
            raise _deny()
        key = qualify_ed25519_host_key(target.host_key, expected_digest=target.host_key_digest)
        if key is None:
            raise _deny()
        # Client and server identities must not reuse the same private key.
        try:
            client_public = target.credential.private_key.public_key().public_bytes(
                serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
            )
        except (TypeError, ValueError, AttributeError):
            raise _deny() from None
        if client_public == key.public_key.encode('ascii'):
            raise _deny()
        aliases.add(target.alias)
        endpoints.add(target.address)


def _write_private_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(content)
    finally:
        os.close(fd)


def _prepare(root: Path, targets: tuple[SSHMaterialTarget, ...]) -> EphemeralSSHFiles:
    known_hosts = root / 'known_hosts'
    config = root / 'ssh_config'
    inventory = root / 'inventory.ini'
    known_lines = []
    configs = []
    for target in sorted(targets, key=lambda item: item.alias):
        key_path = root / (target.alias + '.key')
        private = target.credential.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
        _write_private_file(key_path, private)
        del private
        endpoint = target.address if target.port == 22 else f'[{target.address}]:{target.port}'
        known_lines.append(f'{endpoint} {target.host_key}')
        configs.extend((
            f'Host {target.alias}',
            f'    HostName {target.address}',
            f'    Port {target.port}',
            f'    User {target.credential.username}',
            f'    IdentityFile "{key_path}"',
            '    ProxyCommand none',
            '    ProxyJump none',
        ))
    configs.extend((
        'Host *',
        '    BatchMode yes',
        '    StrictHostKeyChecking yes',
        f'    UserKnownHostsFile "{known_hosts}"',
        '    GlobalKnownHostsFile /dev/null',
        '    CheckHostIP yes',
        '    VerifyHostKeyDNS no',
        '    UpdateHostKeys no',
        '    HostKeyAlgorithms ssh-ed25519',
        '    PubkeyAcceptedAlgorithms ssh-ed25519',
        '    IdentitiesOnly yes',
        '    IdentityAgent none',
        '    PreferredAuthentications publickey',
        '    PasswordAuthentication no',
        '    KbdInteractiveAuthentication no',
        '    GSSAPIAuthentication no',
        '    HostbasedAuthentication no',
        # Unknown aliases cannot use the candidate SSH config for transport.
        '    ProxyCommand /bin/false',
        '    ProxyJump none',
        '    ControlMaster no',
        '    ControlPath none',
        '    ControlPersist no',
        '    ClearAllForwardings yes',
        '    ForwardAgent no',
        '    ForwardX11 no',
        '    PermitLocalCommand no',
        '    CanonicalizeHostname no',
        '    RequestTTY no',
        '    ConnectTimeout 10',
        '    ConnectionAttempts 1',
    ))
    _write_private_file(known_hosts, ('\n'.join(known_lines) + '\n').encode('ascii'))
    _write_private_file(config, ('\n'.join(configs) + '\n').encode('ascii'))
    # No host/user/key variables or provider inputs are interpolated into
    # Ansible inventory. Only validated aliases from this exact SSH bundle.
    inventory_lines = [f'[{REMOTE_GROUP}]', *sorted(target.alias for target in targets)]
    _write_private_file(inventory, ('\n'.join(inventory_lines) + '\n').encode('ascii'))
    return EphemeralSSHFiles(config, known_hosts, inventory)


@contextmanager
def prepare_ephemeral_ssh(targets: tuple[SSHMaterialTarget, ...]) -> Iterator[EphemeralSSHFiles]:
    """Create private tmpfs artifacts and remove them on all ordinary exits.

    Does not call SSH. Future worker must independently authorize and invoke
    only its fixed operation, explicitly using this config, with a sanitized
    environment. Python memory cannot guarantee cryptographic zeroization.
    SIGKILL/worker death requires deployment-level isolated tmpfs teardown.
    """
    _validate_targets(targets)
    try:
        parent = _worker_tmpfs_root()
        with TemporaryDirectory(prefix='kaori-ssh-', dir=parent) as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            yield _prepare(root, targets)
    except (OSError, ValueError, TypeError):
        raise _deny() from None
