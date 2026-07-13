from app.retention.domains.operational_activity import OperationalActivityArchiveDomain

DOMAIN_FACTORIES = {
    'operational_activity': OperationalActivityArchiveDomain,
}


def get_archive_domain(domain_name: str):
    normalized = domain_name.strip().lower().replace('-', '_')
    factory = DOMAIN_FACTORIES.get(normalized)
    if factory is None:
        supported = ', '.join(sorted(DOMAIN_FACTORIES))
        raise ValueError(f'Unsupported archive domain: {domain_name}. Supported domains: {supported}.')
    return factory()


__all__ = [
    'DOMAIN_FACTORIES',
    'OperationalActivityArchiveDomain',
    'get_archive_domain',
]
