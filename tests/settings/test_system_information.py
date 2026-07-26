from packaging.version import Version

from app.integrations.compatibility import PROFILES
from app.settings.system_information import build_system_information


def test_system_information_describes_release_2_1_0_capabilities() -> None:
    information = build_system_information(
        {
            'APP_NAME': 'KAORI',
            'APP_VERSION': '2.1.0',
            'APP_ENV': 'production',
            'APP_BUILD_SHA': 'abc1234',
            'APP_BUILD_DATE': '2026-07-26',
        }
    )

    assert information['version'] == '2.1.0'
    assert information['release_label'] == 'KAORI 2.1.0'
    assert information['environment'] == 'Production'
    assert information['release_highlight_count'] == 3
    assert information['feature_group_count'] == 7
    assert information['feature_count'] >= 30

    capability_titles = {group['title'] for group in information['feature_groups']}
    assert {
        'Kubernetes Platform Operations',
        'Integration Runtime & Compatibility',
        'Jobs & Automation',
        'Reporting & Data Lifecycle',
    }.issubset(capability_titles)


def test_compatibility_baselines_are_covered_by_canonical_profiles() -> None:
    information = build_system_information({'APP_VERSION': '2.1.0'})

    assert information['compatibility_product_count'] == 4
    assert information['compatibility_profile_count'] == sum(len(profiles) for profiles in PROFILES.values())

    for product in information['compatibility_products']:
        profiles = PROFILES[product['key']]
        minimum = product['minimum_version']
        recommended = product['recommended_version']

        assert any(profile.matches(minimum) for profile in profiles), product['product']
        assert any(profile.matches(recommended) for profile in profiles), product['product']

        recommended_profile = next(profile for profile in profiles if profile.matches(recommended))
        assert recommended_profile.support_level in {'current', 'supported'}
        assert product['profiles'] == tuple(
            {
                'key': profile.key,
                'version_constraint': profile.version_constraint,
                'support_level': profile.support_level,
            }
            for profile in profiles
        )


def test_recommended_baselines_are_not_older_than_minimum_versions() -> None:
    information = build_system_information({'APP_VERSION': '2.1.0'})

    for product in information['compatibility_products']:
        assert Version(product['recommended_version']) >= Version(product['minimum_version'])
