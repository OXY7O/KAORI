from pathlib import Path


def test_canonical_lifecycle_assigns_relationship_without_manual_fk_shim() -> None:
    source = Path('app/integrations/lifecycle.py').read_text(encoding='utf-8')

    assert 'provider_record.integration_instance = canonical' in source
    assert 'db.session.add(canonical)' in source
    assert 'provider_record.integration_instance_id = canonical.id' not in source
    assert 'db.session.flush([canonical])' not in source


def test_canonical_lifecycle_leaves_flush_and_commit_to_the_use_case_owner() -> None:
    source = Path('app/integrations/lifecycle.py').read_text(encoding='utf-8')
    creation_block = source.split('if canonical is None:', 1)[1].split(
        'if canonical.provider_type != provider_type:', 1
    )[0]

    assert 'db.session.flush(' not in creation_block
    assert 'db.session.commit(' not in creation_block
    assert creation_block.index('provider_record.integration_instance = canonical') < creation_block.index(
        'db.session.add(canonical)'
    )
