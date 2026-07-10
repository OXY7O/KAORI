def bytes_to_human(
    value: float,
) -> str:
    units = (
        'B',
        'KiB',
        'MiB',
        'GiB',
        'TiB',
    )

    size = float(value)

    for unit in units:
        if size < 1024:
            return f'{size:.2f} {unit}'

        size /= 1024

    return f'{size:.2f} PiB'
