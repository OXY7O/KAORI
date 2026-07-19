from pathlib import Path


def test_canonical_lifecycle_flushes_only_canonical_identity_first() -> None:
    source = Path('app/integrations/lifecycle.py').read_text(encoding='utf-8')

    assert 'db.session.flush([canonical])' in source
    assert 'provider_record.integration_instance_id = canonical.id' in source


def test_canonical_lifecycle_does_not_flush_whole_session_before_fk_assignment() -> None:
    source = Path('app/integrations/lifecycle.py').read_text(encoding='utf-8')
    creation_block = source.split('if canonical is None:', 1)[1].split('canonical.name =', 1)[0]

    assert 'db.session.flush()' not in creation_block
    assert creation_block.index('db.session.flush([canonical])') < creation_block.index(
        'provider_record.integration_instance_id = canonical.id'
    )
