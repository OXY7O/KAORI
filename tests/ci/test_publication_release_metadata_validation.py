"""Fail-closed regression coverage for release metadata shape and identity (#4212)."""

import json
import subprocess

import pytest

from scripts.publication_release_assets_inventory import inventory


def _release(rid=1, assets=None, draft=False, prerelease=False):
    return {'id': rid, 'draft': draft, 'prerelease': prerelease, 'assets': [] if assets is None else assets}


def _run(pages):
    payload = json.dumps(pages)

    def runner(command, **kwargs):
        assert command[:4] == ['gh', 'api', '--paginate', '--slurp']
        assert kwargs['timeout'] == 30
        return subprocess.CompletedProcess(command, 0, payload)

    return inventory('OXY7O/KAORI', runner=runner)


@pytest.mark.parametrize(
    'pages',
    [
        [],
        [None],
        [{}],
        [[None]],
        [[], [_release(rid=1)]],
        [[_release(rid=1)], [], [_release(rid=2)]],
        [[_release(rid=0)]],
        [[_release(rid=True)]],
        [[_release(rid=1), _release(rid=1)]],
        [[_release(rid=1)], [_release(rid=1)]],
        [[_release(draft=1)]],
        [[_release(prerelease=None)]],
        [[_release(assets={})]],
        [[_release(assets=[None])]],
        [[_release(assets=[{'id': 0}])]],
        [[_release(assets=[{'id': True}])]],
        [[_release(assets=[{'id': 3}, {'id': 3}])]],
        [[_release(rid=1, assets=[{'id': 3}])], [_release(rid=2, assets=[{'id': 3}])]],
    ],
)
def test_invalid_release_metadata_fails_closed(pages):
    result = _run(pages)
    assert result['assessment'] == 'INCOMPLETE'
    assert result['release_metadata_access'] == 'FAILED_OR_INCOMPLETE'
    assert result['release_count'] is None
    assert result['asset_count'] is None


def test_valid_multi_page_inventory_is_counted_without_exposing_metadata():
    pages = [
        [_release(rid=1, assets=[{'id': 11, 'name': 'PRIVATE_ASSET'}], draft=True)],
        [_release(rid=2, assets=[{'id': 12}], prerelease=True)],
    ]
    result = _run(pages)
    assert result['assessment'] == 'INCOMPLETE'
    assert result['release_metadata_access'] == 'READ'
    assert (result['release_count'], result['asset_count'], result['draft_count'], result['prerelease_count']) == (
        2,
        2,
        1,
        1,
    )
    assert 'PRIVATE_ASSET' not in json.dumps(result)


def test_terminal_empty_page_does_not_imply_historical_clearance():
    result = _run([[_release(rid=1)], []])
    assert result['release_metadata_access'] == 'READ'
    assert result['release_count'] == 1
    assert result['assessment'] == 'INCOMPLETE'
