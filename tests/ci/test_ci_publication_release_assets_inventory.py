"""Contract tests for sanitized GitHub Release metadata inventory (#4212)."""

import importlib.util
import json
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / 'scripts' / 'publication_release_assets_inventory.py'
spec = importlib.util.spec_from_file_location('publication_release_assets_inventory', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake(pages, returncode=0):
    def runner(command, **kwargs):
        assert command == ['gh', 'api', '--paginate', '--slurp', 'repos/OXY7O/KAORI/releases?per_page=100']
        assert kwargs['timeout'] == 30
        return subprocess.CompletedProcess(command, returncode, json.dumps(pages), 'secret-error')

    return runner


def test_empty_release_listing_is_read_but_never_cleared():
    result = module.inventory('OXY7O/KAORI', fake([[]]))
    assert result['release_metadata_access'] == 'READ'
    assert result['release_count'] == result['asset_count'] == 0
    assert result['assessment'] == 'INCOMPLETE'


def test_counts_paginated_releases_and_assets_without_exposing_metadata():
    pages = [
        [
            {
                'id': 1,
                'draft': False,
                'prerelease': True,
                'assets': [{'id': 11, 'name': 'private-name'}],
                'body': 'secret-value',
            }
        ],
        [{'id': 2, 'draft': True, 'prerelease': False, 'assets': [{'id': 12}]}],
    ]
    result = module.inventory('OXY7O/KAORI', fake(pages))
    assert (result['release_count'], result['asset_count'], result['draft_count'], result['prerelease_count']) == (
        2,
        2,
        1,
        1,
    )
    assert 'private-name' not in json.dumps(result)
    assert 'secret-value' not in json.dumps(result)


def test_duplicate_release_or_asset_ids_fail_closed():
    for pages in (
        [
            [
                {'id': 1, 'draft': False, 'prerelease': False, 'assets': []},
                {'id': 1, 'draft': False, 'prerelease': False, 'assets': []},
            ]
        ],
        [
            [
                {'id': 1, 'draft': False, 'prerelease': False, 'assets': [{'id': 9}]},
                {'id': 2, 'draft': False, 'prerelease': False, 'assets': [{'id': 9}]},
            ]
        ],
    ):
        result = module.inventory('OXY7O/KAORI', fake([pages]))
        assert result['release_metadata_access'] == 'FAILED_OR_INCOMPLETE'
        assert result['asset_count'] is None


def test_malformed_payloads_fail_closed():
    for pages in (
        [],
        {},
        [[{'id': True, 'draft': False, 'prerelease': False, 'assets': []}]],
        [[{'id': 1, 'draft': 0, 'prerelease': False, 'assets': []}]],
        [[{'id': 1, 'draft': False, 'prerelease': False, 'assets': {}}]],
        [[{'id': 1, 'draft': False, 'prerelease': False, 'assets': [{'id': 0}]}]],
    ):
        assert module.inventory('OXY7O/KAORI', fake(pages))['release_count'] is None


def test_api_failure_and_timeout_fail_closed():
    assert module.inventory('OXY7O/KAORI', fake([[]], 1))['release_count'] is None

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('gh', 30)

    assert module.inventory('OXY7O/KAORI', timeout)['release_count'] is None


def test_invalid_repository_never_calls_cli():
    def forbidden(*args, **kwargs):
        raise AssertionError('runner must not be invoked')

    for repo in ('../KAORI', 'OXY7O/..', 'OXY7O/KAORI/extra', 123):
        try:
            module.inventory(repo, forbidden)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid repository accepted')


def test_oversized_response_fails_closed_without_echoing_content(monkeypatch):
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 20)
    result = module.inventory(
        'OXY7O/KAORI', fake([[{'id': 1, 'draft': False, 'prerelease': False, 'assets': [], 'body': 'private-value'}]])
    )
    assert result['release_metadata_access'] == 'FAILED_OR_INCOMPLETE'
    assert result['release_count'] is None
    assert 'private-value' not in json.dumps(result)


def test_page_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(module, 'MAX_PAGES', 1)
    result = module.inventory('OXY7O/KAORI', fake([[], []]))
    assert result['release_metadata_access'] == 'FAILED_OR_INCOMPLETE'


def test_asset_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(module, 'MAX_ASSETS', 1)
    release = {'id': 1, 'draft': False, 'prerelease': False, 'assets': [{'id': 1}, {'id': 2}]}
    result = module.inventory('OXY7O/KAORI', fake([[release]]))
    assert result['asset_count'] is None
    assert result['assessment'] == 'INCOMPLETE'
