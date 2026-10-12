from __future__ import annotations

import pytest

from app.integrations.registry.providers.harbor.client import HarborClient
from app.integrations.registry.providers.harbor.exceptions import HarborResponseError
from app.integrations.registry.providers.harbor.inventory import (
    _artifact_record,
    _project_record,
    _repository_record,
    _validated_tags,
)


@pytest.mark.parametrize('value', ['invalid', [42], [{'name': ''}], [{'id': 2}]])
def test_malformed_artifact_tags_are_not_silently_dropped(value) -> None:
    with pytest.raises(HarborResponseError):
        _validated_tags(value, digest='sha256:abc')


def test_valid_unset_tags_mean_empty() -> None:
    assert _validated_tags(None, digest='sha256:abc') == []
    assert _validated_tags([], digest='sha256:abc') == []


@pytest.mark.parametrize('payload', [{'digest': ''}, {'id': 2}])
def test_artifact_missing_immutable_digest_fails(payload) -> None:
    with pytest.raises(HarborResponseError, match='digest'):
        _artifact_record(payload)


def test_missing_project_and_repository_identity_fail_before_commit() -> None:
    with pytest.raises(HarborResponseError, match='unnamed'):
        _project_record(None, {'project_id': 7})
    with pytest.raises(HarborResponseError, match='unnamed'):
        _repository_record(None, 'team', {'id': 4})


@pytest.mark.parametrize('items', [[{'id': 1}, None], [12], [{} , 'broken']])
def test_harbor_list_rejects_malformed_members_instead_of_partial_success(items) -> None:
    with pytest.raises(HarborResponseError, match='malformed'):
        HarborClient._object_list(items, 'projects')


def test_harbor_complete_valid_empty_collection_remains_valid() -> None:
    assert HarborClient._object_list([], 'projects') == []
