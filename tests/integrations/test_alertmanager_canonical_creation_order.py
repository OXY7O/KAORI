from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_alertmanager_canonical_identity_is_created_before_provider_flush() -> None:
    source = (ROOT / 'app/alertmanager/service.py').read_text()
    marker = "instance.last_validated_at = None"
    block = source[source.index(marker):source.index("    if commit:", source.index(marker))]

    canonical_index = block.index(
        "ensure_canonical_instance(instance, provider_type='alertmanager')"
    )
    flush_index = block.index('db.session.flush()')

    assert canonical_index < flush_index
    assert block.count(
        "ensure_canonical_instance(instance, provider_type='alertmanager')"
    ) == 2
