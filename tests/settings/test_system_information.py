from app.settings.system_information import build_system_information


def test_system_information_describes_release_2_3_0_capabilities() -> None:
    information = build_system_information(
        {
            'APP_NAME': 'KAORI',
            'APP_VERSION': '2.3.0',
            'APP_ENV': 'production',
            'APP_BUILD_SHA': 'abc1234',
            'APP_BUILD_DATE': '2026-07-26',
        }
    )

    assert information['version'] == '2.3.0'
    assert information['release_label'] == 'KAORI 2.3.0'
    assert information['environment'] == 'Production'
    assert information['release_highlight_count'] == 3
    assert information['feature_group_count'] == 7
    assert information['feature_count'] >= 30


def test_compatibility_matrix_separates_contracts_qualifications_and_lifecycle() -> None:
    information = build_system_information({'APP_VERSION': '2.3.0'})

    assert information['compatibility_policy_key'] == 'kaori-compatibility-policy-v1'
    assert information['compatibility_policy_version'] == 1
    assert information['compatibility_policy_year'] == 2026
    assert information['compatibility_lookback_years'] == 5
    assert information['compatibility_anchor_year'] == 2021
    assert information['compatibility_window_label'] == '2021–2026'
    assert information['compatibility_product_count'] == 5
    assert information['compatibility_contract_count'] == 4
    assert information['compatibility_qualification_count'] >= 9

    products = {item['key']: item for item in information['compatibility_products']}

    assert products['kubernetes']['contract_profile'] == 'kubernetes-core-v1'
    assert products['kubernetes']['minimum_label'] == 'v1.23'
    assert products['kubernetes']['recommended_label'] == 'v1.37.x'
    assert products['kubernetes']['policy_version'] == 'v1'
    assert products['kubernetes']['policy_window'] == '2021–2026'
    assert 'v1.35–v1.37' in products['kubernetes']['upstream_lifecycle']

    assert products['prometheus']['contract_profile'] == 'prometheus-http-core-v1'
    assert products['thanos']['contract_profile'] == 'prometheus-http-core-v1'
    assert products['prometheus']['minimum_label'] == 'v2.32'
    assert products['thanos']['minimum_label'] == 'v0.24'
    assert products['thanos']['recommended_label'] == 'v0.42.4'

    assert products['alertmanager']['contract_profile'] == 'alertmanager-api-v2-contract-v1'
    assert products['alertmanager']['minimum_label'] == 'v0.23'
    assert products['alertmanager']['recommended_label'] == 'v0.34.1'
    assert products['alertmanager']['qualified_versions'] == 'v0.23–v0.34.x'

    assert products['minio']['contract_profile'] == 's3-object-storage-v1'
    assert 'RELEASE.2021-12-29T06-49-06Z' in products['minio']['qualified_versions']
    assert 'RELEASE.2025-10-15T17-29-55Z' in products['minio']['qualified_versions']
    assert 'archived' in products['minio']['upstream_lifecycle'].lower()


def test_qualification_rows_map_to_the_displayed_general_contract() -> None:
    information = build_system_information({'APP_VERSION': '2.3.0'})

    for product in information['compatibility_products']:
        assert product['profile_count'] == len(product['profiles'])
        assert all(profile['contract_profile'] == product['contract_profile'] for profile in product['profiles'])
