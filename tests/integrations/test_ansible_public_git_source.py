"""Provider-owned GitHub public source verification: real blob identities and negative cases."""

from __future__ import annotations

from dataclasses import replace

import pytest
from flask import Flask

from app.integrations.orchestration.configuration_automation.providers.ansible.contract import (
    AnsibleConnectionInput,
    require_registration_policy,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.proof import (
    issue_source_proof,
    verified_source_proof,
)
from app.integrations.source_control.source_control.providers.github import public_automation_source as source


class Response:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.payload = payload
        self.closed = False

    def iter_content(self, chunk_size=16384):
        import json

        yield json.dumps(self.payload).encode('utf-8')

    def close(self):
        self.closed = True


class Session:
    def __init__(self, data):
        self.responses = list(data)
        self.urls = []
        self.trust_env = True
        self.closed = False

    def get(self, url, **kwargs):
        assert kwargs['verify'] is True
        assert kwargs['allow_redirects'] is False
        assert kwargs['stream'] is True
        assert kwargs['timeout'] == (3, 10)
        self.urls.append(url)
        assert url.startswith('https://api.github.com/repos/OXY7O/kaori-operations/git/')
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def valid_source(**changes):
    tree_sha = 'a' * 40
    blob_map = [
        {'path': name, 'sha': sha, 'type': 'blob', 'mode': '100644'} for name, sha in source._REQUIRED_BLOBS.items()
    ]
    base = {
        'sha': tree_sha,
        'truncated': False,
        'tree': blob_map,
    }
    base.update(changes)
    session = Session(
        [
            Response({'sha': source.SOURCE_CANDIDATE_SHA, 'tree': {'sha': tree_sha}}),
            Response(base),
        ]
    )
    return session


def values(**kwargs):
    basic = AnsibleConnectionInput(
        name='Kubespray Sandbox',
        description='source-only',
        environment='laboratory',
        profile_key=source.PROFILE_KEY,
        repository=source.REPOSITORY,
        revision=source.SOURCE_CANDIDATE_SHA,
        ansible_core_version=source.ANSIBLE_CORE_VERSION,
        ansible_runner_version=source.ANSIBLE_RUNNER_VERSION,
        kubespray_release=source.KUBESPRAY_RELEASE,
        execution_environment_digest=None,
    )
    return replace(basic, **kwargs)


def test_real_git_tree_and_blob_checks_are_required_before_source_proof() -> None:
    session = valid_source()
    evidence = source.verify_public_kubespray_source(
        source.REPOSITORY, source.SOURCE_CANDIDATE_SHA, session_factory=lambda: session
    )
    assert evidence.checked_files == 5
    assert evidence.profile_key == 'kubernetes_lifecycle'
    assert evidence.as_dict()['operation_authorized'] is False
    assert session.trust_env is False
    assert session.closed
    assert len(session.urls) == 2


@pytest.mark.parametrize(
    'invalid',
    [
        {'truncated': True},
        {'tree': []},
        {'tree': [{'path': 'automation/operations.json', 'sha': '0' * 40, 'type': 'blob', 'mode': '100644'}]},
        {'sha': 'b' * 40},
    ],
)
def test_missing_or_changed_git_source_fails_closed(invalid):
    session = valid_source(**invalid)
    with pytest.raises(source.AutomationSourceRejected):
        source.verify_public_kubespray_source(
            source.REPOSITORY, source.SOURCE_CANDIDATE_SHA, session_factory=lambda: session
        )


def test_unapproved_repository_or_sha_never_opens_network_session():
    for repository, sha in [('Evil/Private', source.SOURCE_CANDIDATE_SHA), (source.REPOSITORY, '0' * 40)]:
        with pytest.raises(source.AutomationSourceRejected):
            source.verify_public_kubespray_source(
                repository, sha, session_factory=lambda: (_ for _ in ()).throw(AssertionError('network call'))
            )


@pytest.mark.parametrize(
    'field,value',
    [
        ('environment', 'production'),
        ('profile_key', 'arbitrary_playbook'),
        ('repository', 'other/repo'),
        ('revision', 'main'),
        ('ansible_core_version', 'latest'),
        ('ansible_core_version', '2.19.3'),
        ('revision', '831ab7c114b1c1ba777c08ab79c91415ad8d465d'),
        ('ansible_runner_version', 'latest'),
        ('kubespray_release', 'v2.1.0'),
        ('execution_environment_digest', 'sha256:bad'),
    ],
)
def test_registration_policy_rejects_unapproved_versions_and_environments(field, value):
    with pytest.raises(ValueError):
        require_registration_policy(replace(values(), **{field: value}))


def test_user_bound_short_lived_source_proof_rejects_changed_values():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-source-proof'
    with app.app_context():
        session = valid_source()
        evidence = source.verify_public_kubespray_source(
            source.REPOSITORY, source.SOURCE_CANDIDATE_SHA, session_factory=lambda: session
        )
        token = issue_source_proof(values(), evidence, user_id=101)
        assert verified_source_proof(token, values(), user_id=101) is not None
        assert verified_source_proof(token, values(), user_id=102) is None
        assert verified_source_proof(token, values(name='Modified Name'), user_id=101) is None
        assert verified_source_proof('invalid-token', values(), user_id=101) is None
        assert verified_source_proof('', values(), user_id=101) is None


def test_accepted_profile_pins_match_reviewed_upstream_merge():
    assert source.SOURCE_CANDIDATE_SHA == '63db48309cbb6d261c27cf54f60bfe885a21f770'
    assert source.ANSIBLE_CORE_VERSION == '2.19.15'
    assert source.ANSIBLE_RUNNER_VERSION == '2.4.3'
    assert source._REQUIRED_BLOBS['execution-environments/requirements.txt'] == (
        '1765812c981fc4bca9acd782a4f6584c7ce0e8bb'
    )
    assert source._REQUIRED_BLOBS['kubernetes/self-managed/profiles/kubespray-v2.32.0-pilot.json'] == (
        'b8f50d37f61392b11ff22cc7bfd3586796dc4c92'
    )


def test_superseded_source_does_not_open_transport():
    with pytest.raises(source.AutomationSourceRejected):
        source.verify_public_kubespray_source(
            source.REPOSITORY,
            '831ab7c114b1c1ba777c08ab79c91415ad8d465d',
            session_factory=lambda: (_ for _ in ()).throw(AssertionError('network call')),
        )


def test_old_requirements_blob_is_rejected_even_at_current_revision():
    entries = [
        {'path': name, 'sha': sha, 'type': 'blob', 'mode': '100644'} for name, sha in source._REQUIRED_BLOBS.items()
    ]
    for entry in entries:
        if entry['path'] == 'execution-environments/requirements.txt':
            entry['sha'] = '78ac0ec89316f0c02799afbdedddab88e0ef27b6'
    with pytest.raises(source.AutomationSourceRejected):
        source.verify_public_kubespray_source(
            source.REPOSITORY, source.SOURCE_CANDIDATE_SHA, session_factory=lambda: valid_source(tree=entries)
        )
