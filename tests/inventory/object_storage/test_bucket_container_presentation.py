from app.inventory.object_storage.presentation import (
    _native_type_label,
    _protection_posture,
    _provider_detail_sections,
    _state_view,
)


def test_native_type_labels_are_provider_neutral() -> None:
    assert _native_type_label('bucket') == 'Bucket'
    assert _native_type_label('container') == 'Container'
    assert _native_type_label('custom_namespace') == 'Custom Namespace'


def test_uncollected_protection_does_not_claim_provider_security() -> None:
    posture = _protection_posture(
        versioning_state='not_collected',
        immutability_state='not_collected',
        encryption_state='not_collected',
        exposure_state='not_collected',
    )
    assert posture == {'label': 'Not Assessed', 'tone': 'unknown'}


def test_public_exposure_is_a_high_priority_cross_provider_signal() -> None:
    posture = _protection_posture(
        versioning_state='enabled',
        immutability_state='enabled',
        encryption_state='enabled',
        exposure_state='public',
    )
    assert posture == {'label': 'Attention', 'tone': 'critical'}


def test_fully_observed_protection_is_normalized_as_protected() -> None:
    posture = _protection_posture(
        versioning_state='enabled',
        immutability_state='configured',
        encryption_state='enabled',
        exposure_state='private',
    )
    assert posture == {'label': 'Protected', 'tone': 'normal'}


def test_state_view_distinguishes_not_supported_from_not_assessed() -> None:
    assert _state_view('not_supported')['label'] == 'Not Supported'
    assert _state_view('not_collected')['label'] == 'Not Assessed'


def test_provider_detail_sections_keep_native_evidence_outside_canonical_fields() -> None:
    sections = _provider_detail_sections(
        provider_metadata={
            'sections': [
                {
                    'title': 'MinIO Bucket Configuration',
                    'description': 'Provider-native S3 configuration evidence.',
                    'icon': 'settings-2',
                    'rows': [
                        {'label': 'Quota Mode', 'value': 'Hard'},
                        {'label': 'Native Rule Count', 'value': 3},
                    ],
                }
            ]
        },
    )
    assert sections[0]['title'] == 'MinIO Bucket Configuration'
    labels = {row['label'] for row in sections[0]['rows']}
    assert {'Quota Mode', 'Native Rule Count'} <= labels
