from __future__ import annotations

import ast
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
HERO = TEMPLATES / 'components' / 'page_hero.html'
STANDARD = ROOT / 'docs' / 'design' / 'components' / 'HERO.md'
DARK_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'DARK_MODE.md'
ANALYTICS_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'ANALYTICS_HERO.md'
DASHBOARD_STANDARD = ROOT / 'docs' / 'design' / 'patterns' / 'OPERATIONAL_DASHBOARD.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'
INTEGRATION_TAXONOMY = ROOT / 'app' / 'definitions' / 'catalogs' / 'integrations' / 'taxonomy.yaml'
INTEGRATION_DOMAIN_HERO = TEMPLATES / 'integrations' / 'domain.html'
INTEGRATION_OVERVIEW = TEMPLATES / 'integrations' / 'overview.html'
INTEGRATION_OVERVIEW_HERO = TEMPLATES / 'integrations' / 'partials' / '_hero.html'
REPORTS_UNAVAILABLE_HERO = TEMPLATES / 'reports' / '_unavailable.html'
REPORTS_WEB = ROOT / 'app' / 'reports' / 'web.py'
REPORTS_PAGE_SUBTITLE_HEROES = {
    TEMPLATES / 'reports' / 'generate' / 'index.html',
    TEMPLATES / 'reports' / 'overview' / 'index.html',
    TEMPLATES / 'reports' / 'report_templates' / 'index.html',
    TEMPLATES / 'reports' / 'schedules' / 'index.html',
    TEMPLATES / 'reports' / 'storage' / 'index.html',
}
REPORTS_PAGE_SUBTITLE_DOMAINS = {'generate', 'overview', 'report_templates', 'schedules', 'storage'}
KUBERNETES_ANALYTICS_BLOCKED_HERO = TEMPLATES / 'kubernetes' / 'analytics' / 'materialization' / 'blocked.html'
KUBERNETES_ANALYTICS_MATERIALIZATION_PRESENTATION = (
    ROOT / 'app' / 'kubernetes' / 'analytics' / 'materialization' / 'presentation.py'
)
KUBERNETES_ANALYTICS_ROUTES = ROOT / 'app' / 'kubernetes' / 'analytics'
PROVIDER_EDIT_HERO = TEMPLATES / 'integrations' / 'components' / '_provider_edit_hero.html'
PROVIDER_REGISTRATION_HERO = TEMPLATES / 'integrations' / 'components' / '_provider_registration_hero.html'
PROVIDER_FRONTPAGE_HERO = TEMPLATES / 'integrations' / 'components' / '_provider_frontpage.html'
PROVIDER_DYNAMIC_DESCRIPTION_OWNERS = {
    (PROVIDER_EDIT_HERO, 'description'),
    (PROVIDER_REGISTRATION_HERO, 'description'),
    (PROVIDER_FRONTPAGE_HERO, 'description'),
    (INTEGRATION_OVERVIEW_HERO, 'description'),
    (TEMPLATES / 'kubernetes' / 'operations' / 'cluster_required.html', 'requested_page_description'),
}

DESCRIPTION_MIN_WORDS = 7
DESCRIPTION_MAX_WORDS = 15
DESCRIPTION_PREFERRED_MIN_WORDS = 8
DESCRIPTION_PREFERRED_MAX_WORDS = 12
DESCRIPTION_MAX_CHARS = 110
DESCRIPTION_ACTION_STARTERS = frozenset(
    {
        'access',
        'add',
        'analyze',
        'assess',
        'audit',
        'browse',
        'build',
        'check',
        'compare',
        'configure',
        'connect',
        'control',
        'create',
        'define',
        'delete',
        'discover',
        'edit',
        'evaluate',
        'examine',
        'explore',
        'generate',
        'govern',
        'identify',
        'inspect',
        'investigate',
        'keep',
        'maintain',
        'manage',
        'monitor',
        'observe',
        'open',
        'operate',
        'optimize',
        'plan',
        'prepare',
        'protect',
        'publish',
        'reconcile',
        'register',
        'replace',
        'resolve',
        'restore',
        'review',
        'rotate',
        'run',
        'schedule',
        'see',
        'select',
        'set',
        'surface',
        'track',
        'understand',
        'update',
        'use',
        'validate',
        'verify',
        'view',
    }
)
CLUSTER_REQUIRED_CONTEXT_SUFFIX = 'in KAORI.'
PROVIDER_EDIT_SHORT_DESCRIPTION_SUFFIX = 'Maintain governed validation and consumer-binding context.'
REPORTS_UNAVAILABLE_SHORT_DESCRIPTION_SUFFIX = 'Maintain governed recovery and retained evidence context.'
DESCRIPTION_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
DESCRIPTION_PARAGRAPH_PATTERN = re.compile(
    r'<p\b(?=[^>]*page_hero\.description_classes\(\))[^>]*>(?P<body>.*?)</p>',
    flags=re.IGNORECASE | re.DOTALL,
)
JINJA_DESCRIPTION_VARIABLE_PATTERN = re.compile(r'^\s*{{\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*}}\s*$')
OPERATIONAL_DASHBOARD_DESCRIPTION_PATTERN = re.compile(
    r"page_hero\.operational_dashboard\(\s*'[^']*',\s*'[^']*',\s*'[^']*',"
    r"\s*'(?P<description>[^']*)'",
    flags=re.DOTALL,
)
PROVIDER_HERO_CALL_PATTERN = re.compile(
    r'provider_(?P<kind>edit|registration)_hero\.render\(\s*'
    r'(?:[^,\n]+,\s*){4}'
    r'(?P<quote>[\'\"])(?P<description>.*?)(?P=quote)\s*,',
    flags=re.DOTALL,
)
PROVIDER_FRONTPAGE_IMPORT_PATTERN = re.compile(
    r'{%\s*import\s+[\'\"]integrations/components/_provider_frontpage\.html[\'\"]\s+as\s+'
    r'(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*%}'
)

KUBERNETES_ANALYTICS_HEROES = (
    TEMPLATES / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'utilization' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'capacity' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'storage' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'workload' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'top_consumers' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'alerts' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'forecast' / 'partials' / '_hero.html',
)
OBJECT_STORAGE_ANALYTICS_HERO = TEMPLATES / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero.html'
OBJECT_STORAGE_ANALYTICS_PAGES = ROOT / 'app' / 'storage' / 'object_storage' / 'analytics' / 'pages.py'
OBJECT_STORAGE_ANALYTICS_PAGE_KEYS = {'overview', 'capacity', 'performance', 'forecast', 'top_consumers', 'alerts'}

REMOVED_MACROS = (
    'context_posture_header',
    'context_posture_note',
    'context_bottom_notice',
    'action_group_classes',
    'secondary_action_classes',
    'destructive_action_classes',
    'supporting_strip',
)
REQUIRED_MACROS = (
    'shell_classes',
    'layout_classes',
    'content_classes',
    'aside_classes',
    'context_panel_classes',
    'context_status_badge',
    'context_card_body',
    'context_card',
    'blocked_context_body',
    'operational_dashboard',
    'context_panel_eyebrow_classes',
    'context_panel_title_classes',
    'context_icon_classes',
    'context_icon_box',
    'context_action_icon_box',
    'context_metric_card_classes',
    'context_metric_label_classes',
    'context_metric_value_classes',
    'context_metric_helper_classes',
    'context_action_classes',
    'context_single_action_classes',
    'context_header',
    'context_header_action',
    'context_header_status',
    'context_actions_classes',
    'context_info',
    'context_panel_metrics_classes',
    'context_metric',
    'title_classes',
    'description_classes',
    'metadata_row_classes',
    'persistent_metadata',
    'analytics_metadata',
    'intro',
    'meta_label',
)


def _read(path: Path) -> str:
    if not path.exists():
        relative = path.relative_to(ROOT)
        raise AssertionError(f'Missing required Hero standard file: {relative}')
    return path.read_text(encoding='utf-8')


def _require_tokens(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        joined = ', '.join(missing)
        raise AssertionError(f'{owner}: missing canonical tokens: {joined}')


def _macro_names(source: str) -> set[str]:
    return set(re.findall(r'{%\s*macro\s+([A-Za-z0-9_]+)', source))


def _description_words(text: str) -> list[str]:
    return DESCRIPTION_WORD_PATTERN.findall(text)


def _effective_short_description(description: str, suffix: str) -> str:
    if len(_description_words(description)) >= DESCRIPTION_MIN_WORDS:
        return description
    return f'{description} {suffix}'


def _validate_description_budget(text: str, *, owner: str) -> None:
    description = text.strip()
    character_count = len(description)
    words = _description_words(description)
    word_count = len(words)
    if '\n' in description or '\r' in description:
        raise AssertionError(f'{owner}: Hero description must not contain a manual line break')
    if not description.endswith(('.', '!', '?')):
        raise AssertionError(f'{owner}: Hero description must be one complete short sentence')
    if not DESCRIPTION_MIN_WORDS <= word_count <= DESCRIPTION_MAX_WORDS:
        raise AssertionError(
            f'{owner}: Hero description has {word_count} words; expected '
            f'{DESCRIPTION_MIN_WORDS}-{DESCRIPTION_MAX_WORDS} words; value={description!r}'
        )
    if character_count > DESCRIPTION_MAX_CHARS:
        raise AssertionError(
            f'{owner}: Hero description has {character_count} characters; maximum '
            f'{DESCRIPTION_MAX_CHARS} characters; value={description!r}'
        )
    first_word = words[0].lower()
    if first_word not in DESCRIPTION_ACTION_STARTERS:
        raise AssertionError(
            f'{owner}: Hero description must be action-oriented and start with an approved action verb; '
            f'found {words[0]!r}; value={description!r}'
        )


def _has_unmanaged_hero_shell(source: str) -> bool:
    openings = re.finditer(
        r'<(?P<tag>section|header)\b(?P<attrs>[^>]*)>',
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for opening in openings:
        attrs = opening.group('attrs')
        has_surface = re.search(
            r'class\s*=\s*["\'][^"\']*(?:bg-kaori-primary|kaori-hero-shell)'
            r'[^"\']*["\']',
            attrs,
            flags=re.DOTALL,
        )
        if not has_surface:
            continue
        tag = opening.group('tag')
        remainder = source[opening.end() :]
        closing = re.search(rf'</{tag}\s*>', remainder, flags=re.IGNORECASE)
        if closing and re.search(r'<h1\b', remainder[: closing.start()], flags=re.IGNORECASE):
            return True
    return False


def _primitive_shell_templates() -> list[Path]:
    return sorted(
        path
        for path in TEMPLATES.rglob('*.html')
        if path != HERO and 'page_hero.shell_classes()' in path.read_text(encoding='utf-8')
    )


def _profile_templates() -> list[Path]:
    return sorted(
        path
        for path in TEMPLATES.rglob('*.html')
        if path != HERO and 'page_hero.operational_dashboard(' in path.read_text(encoding='utf-8')
    )


def _normalize_description_text(value: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', value)
    return html.unescape(' '.join(text.split()))


def _local_jinja_literal_values(source: str, variable: str) -> list[str]:
    assignment_pattern = re.compile(
        r'{%\s*set\s+' + re.escape(variable) + r'\s*=\s*(?P<quote>[\'\"])(?P<value>.*?)(?P=quote)\s*%}',
        flags=re.DOTALL,
    )
    return [
        _normalize_description_text(match.group('value'))
        for match in assignment_pattern.finditer(source)
        if _normalize_description_text(match.group('value'))
    ]


def _inline_jinja_literal_values(body: str) -> list[str]:
    expression_match = re.fullmatch(r'\s*{{\s*(?P<expression>.*?)\s*}}\s*', body, flags=re.DOTALL)
    if not expression_match:
        return []
    try:
        node = ast.parse(expression_match.group('expression'), mode='eval').body
    except SyntaxError:
        return []

    def collect(current: ast.AST) -> list[str]:
        if isinstance(current, ast.Constant) and isinstance(current.value, str):
            return [current.value]
        if isinstance(current, ast.IfExp):
            body_values = collect(current.body)
            else_values = collect(current.orelse)
            if body_values and else_values:
                return [*body_values, *else_values]
        return []

    return [normalized for value in collect(node) if (normalized := _normalize_description_text(value))]


def _conditional_jinja_literal_values(body: str) -> list[str]:
    control_pattern = re.compile(r'{%\s*(?P<tag>if|elif|else|endif)\b.*?%}', flags=re.DOTALL)
    controls = list(control_pattern.finditer(body))
    if not controls or controls[0].group('tag') != 'if' or controls[-1].group('tag') != 'endif':
        return []
    if re.sub(control_pattern, '', body).count('{%'):
        return []

    values: list[str] = []
    for index, control in enumerate(controls[:-1]):
        tag = control.group('tag')
        if tag not in {'if', 'elif', 'else'}:
            return []
        segment_start = control.end()
        segment_end = controls[index + 1].start()
        segment = body[segment_start:segment_end]
        resolved = re.sub(r'{{\s*[^}]+\s*}}', 'value', segment)
        if '{{' in resolved or '{%' in resolved:
            return []
        text = _normalize_description_text(resolved)
        if text:
            values.append(text)
    return values


def _has_registered_description_resolver(path: Path, variable: str) -> bool:
    materialization_description = (
        path.parent == KUBERNETES_ANALYTICS_BLOCKED_HERO.parent
        and path.name in {'blocked.html', 'pending.html'}
        and variable == 'materialization_description'
    )
    return (path, variable) in PROVIDER_DYNAMIC_DESCRIPTION_OWNERS or materialization_description


def _has_registered_dynamic_expression_resolver(path: Path, body: str) -> bool:
    normalized = ' '.join(body.split())
    return (
        path == INTEGRATION_DOMAIN_HERO
        and normalized == '{{ domain.description }}'
        or path == REPORTS_UNAVAILABLE_HERO
        and normalized == '{{ payload.description }}'
        or path in REPORTS_PAGE_SUBTITLE_HEROES
        and normalized == '{{ payload.page_subtitle }}'
        or path == OBJECT_STORAGE_ANALYTICS_HERO
        and normalized == '{{ page.description }}'
    )


def _literal_hero_descriptions(paths: list[Path]) -> dict[str, str]:
    """Discover literal and deterministically-resolvable Jinja Hero descriptions.

    A Hero description rendered from a Jinja variable is audited across every
    static assignment in that template. Static inline ternaries and simple
    if/elif/else descriptions are audited branch-by-branch. Variables delegated
    to an explicit source resolver are audited by that resolver; all other
    unresolved dynamic expressions fail closed.
    """
    descriptions: dict[str, str] = {}
    unresolved: list[str] = []
    for path in paths:
        source = _read(path)
        relative = str(path.relative_to(ROOT))
        for index, match in enumerate(DESCRIPTION_PARAGRAPH_PATTERN.finditer(source), start=1):
            body = match.group('body')
            variable_match = JINJA_DESCRIPTION_VARIABLE_PATTERN.fullmatch(body)
            if variable_match:
                variable = variable_match.group('name')
                values = _local_jinja_literal_values(source, variable)
                if values:
                    for variant, value in enumerate(values, start=1):
                        descriptions[f'{relative}#{variable}:{variant}'] = value
                    continue
                if _has_registered_description_resolver(path, variable):
                    continue
                unresolved.append(
                    f'{relative}: Hero description variable {variable!r} has no static local '
                    'assignments or registered verifier resolver'
                )
                continue
            if '{{' in body or '{%' in body:
                values = _inline_jinja_literal_values(body)
                if not values:
                    values = _conditional_jinja_literal_values(body)
                if values:
                    for variant, value in enumerate(values, start=1):
                        descriptions[f'{relative}#dynamic:{variant}'] = value
                    continue
                if _has_registered_dynamic_expression_resolver(path, body):
                    continue
                unresolved.append(
                    f'{relative}: Hero description must be a literal or a statically resolvable Jinja expression'
                )
                continue
            text = _normalize_description_text(body)
            if text:
                owner = relative if index == 1 else f'{relative}#{index}'
                descriptions[owner] = text
    if unresolved:
        raise AssertionError('Unresolved Hero description authorities:\n- ' + '\n- '.join(unresolved))
    return descriptions


def _dashboard_descriptions(paths: list[Path]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for path in paths:
        source = _read(path)
        match = OPERATIONAL_DASHBOARD_DESCRIPTION_PATTERN.search(source)
        if not match:
            relative = path.relative_to(ROOT)
            raise AssertionError(f'{relative}: dashboard description must be a static literal')
        descriptions[str(path.relative_to(ROOT))] = match.group('description')
    return descriptions


def _provider_component_descriptions() -> dict[str, str]:
    _require_tokens(
        _read(PROVIDER_EDIT_HERO),
        (PROVIDER_EDIT_SHORT_DESCRIPTION_SUFFIX, 'description.split()|length < 11'),
        'Integration provider edit Hero description normalization',
    )
    descriptions: dict[str, str] = {}
    frontpage_count = 0
    for path in sorted(TEMPLATES.rglob('*.html')):
        if path in {PROVIDER_EDIT_HERO, PROVIDER_REGISTRATION_HERO, PROVIDER_FRONTPAGE_HERO}:
            continue
        source = _read(path)
        for match in PROVIDER_HERO_CALL_PATTERN.finditer(source):
            description = _normalize_description_text(match.group('description'))
            if not description:
                continue
            if match.group('kind') == 'edit':
                description = _effective_short_description(description, PROVIDER_EDIT_SHORT_DESCRIPTION_SUFFIX)
            line = source.count('\n', 0, match.start()) + 1
            owner = f'provider {match.group("kind")} {path.relative_to(ROOT)}:{line}'
            descriptions[owner] = description

        for import_match in PROVIDER_FRONTPAGE_IMPORT_PATTERN.finditer(source):
            alias = import_match.group('alias')
            call_pattern = re.compile(
                re.escape(alias) + r'\.hero\(\s*(?:[^,\n]+,\s*){3}(?P<quote>[\'\"])(?P<description>.*?)(?P=quote)\s*,',
                flags=re.DOTALL,
            )
            for match in call_pattern.finditer(source):
                description = _normalize_description_text(match.group('description'))
                if not description:
                    continue
                line = source.count('\n', 0, match.start()) + 1
                descriptions[f'provider frontpage {path.relative_to(ROOT)}:{line}'] = description
                frontpage_count += 1

    if not any(
        owner.startswith('provider edit ') or owner.startswith('provider registration ') for owner in descriptions
    ):
        raise AssertionError('Integration provider Hero: no static edit/registration descriptions discovered')
    if frontpage_count == 0:
        raise AssertionError('Integration provider frontpage Hero: no static descriptions discovered')
    return descriptions


def _integration_overview_descriptions() -> dict[str, str]:
    values = _local_jinja_literal_values(_read(INTEGRATION_OVERVIEW), 'description')
    if not values:
        raise AssertionError('Integration overview Hero: no static description source discovered')
    return {f'Integration overview:{index}': value for index, value in enumerate(values, start=1)}


def _clean_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _integration_domain_descriptions() -> dict[str, str]:
    taxonomy = _read(INTEGRATION_TAXONOMY)
    domains = taxonomy.split('\ncapabilities:', 1)[0]
    entries = re.finditer(
        r'(?ms)^- key: [^\n]+\n\s+label: (?P<label>[^\n]+)\n'
        r'\s+description: (?P<description>[^\n]+)',
        domains,
    )
    result = {
        f'Integration domain {_clean_yaml_scalar(match.group("label"))}': _clean_yaml_scalar(match.group('description'))
        for match in entries
    }
    if not result:
        raise AssertionError('Integration taxonomy: no Hero descriptions discovered')
    return result


def _static_string(node: ast.AST | None, *, owner: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise AssertionError(f'{owner}: Hero copy must be a static string literal')


def _reports_unavailable_descriptions() -> dict[str, str]:
    _require_tokens(
        _read(REPORTS_WEB),
        (REPORTS_UNAVAILABLE_SHORT_DESCRIPTION_SUFFIX, '_normalize_reports_unavailable_description'),
        'Reports unavailable Hero description normalization',
    )
    descriptions: dict[str, str] = {}
    for path in sorted((ROOT / 'app' / 'reports').rglob('*.py')):
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            matched = (
                isinstance(function, ast.Name)
                and function.id == 'render_reports_unavailable'
                or isinstance(function, ast.Attribute)
                and function.attr == 'render_reports_unavailable'
            )
            if not matched:
                continue
            owner = f'reports unavailable {path.relative_to(ROOT)}:{node.lineno}'
            description_node = next(
                (keyword.value for keyword in node.keywords if keyword.arg == 'description'),
                None,
            )
            if description_node is None:
                raise AssertionError(f'{owner}: description is required')
            description = _static_string(description_node, owner=owner)
            descriptions[owner] = _effective_short_description(
                description,
                REPORTS_UNAVAILABLE_SHORT_DESCRIPTION_SUFFIX,
            )
    if not descriptions:
        raise AssertionError('Reports unavailable Hero: no static descriptions discovered')
    return descriptions


def _subscript_string_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return None


def _reports_page_subtitle_descriptions() -> dict[str, str]:
    descriptions: dict[str, str] = {}
    discovered_domains: set[str] = set()
    reports_root = ROOT / 'app' / 'reports'
    for domain in sorted(REPORTS_PAGE_SUBTITLE_DOMAINS):
        domain_root = reports_root / domain
        for path in sorted(domain_root.rglob('*.py')):
            tree = ast.parse(_read(path), filename=str(path))
            for node in ast.walk(tree):
                candidates: list[tuple[int, ast.AST]] = []
                if isinstance(node, ast.Dict):
                    candidates.extend(
                        (node.lineno, value)
                        for key, value in zip(node.keys, node.values, strict=True)
                        if isinstance(key, ast.Constant) and key.value == 'page_subtitle'
                    )
                elif isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'setdefault'
                        and len(node.args) >= 2
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == 'page_subtitle'
                    ):
                        candidates.append((node.lineno, node.args[1]))
                    candidates.extend(
                        (node.lineno, keyword.value) for keyword in node.keywords if keyword.arg == 'page_subtitle'
                    )
                elif isinstance(node, ast.Assign):
                    if any(_subscript_string_key(target) == 'page_subtitle' for target in node.targets):
                        candidates.append((node.lineno, node.value))
                elif isinstance(node, ast.AnnAssign):
                    if _subscript_string_key(node.target) == 'page_subtitle' and node.value is not None:
                        candidates.append((node.lineno, node.value))

                for lineno, value in candidates:
                    owner = f'reports {domain} Hero {path.relative_to(ROOT)}:{lineno}'
                    descriptions[owner] = _static_string(value, owner=owner)
                    discovered_domains.add(domain)

    missing = sorted(REPORTS_PAGE_SUBTITLE_DOMAINS - discovered_domains)
    if missing:
        raise AssertionError('Reports Hero page_subtitle authority missing for: ' + ', '.join(missing))
    return descriptions


def _object_storage_analytics_descriptions() -> dict[str, str]:
    tree = ast.parse(_read(OBJECT_STORAGE_ANALYTICS_PAGES), filename=str(OBJECT_STORAGE_ANALYTICS_PAGES))
    descriptions: dict[str, str] = {}
    discovered_keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == 'PAGES' for target in targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise AssertionError('Object Storage Analytics PAGES must remain a static dictionary')
        for key_node, page_node in zip(node.value.keys, node.value.values, strict=True):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                raise AssertionError('Object Storage Analytics page keys must remain static strings')
            page_key = key_node.value
            if page_key not in OBJECT_STORAGE_ANALYTICS_PAGE_KEYS:
                continue
            if not isinstance(page_node, ast.Call) or len(page_node.args) < 2:
                raise AssertionError(f'Object Storage Analytics {page_key}: PageDefinition must own static description')
            owner = f'Object Storage Analytics {page_key}'
            descriptions[owner] = _static_string(page_node.args[1], owner=owner)
            discovered_keys.add(page_key)

    missing = sorted(OBJECT_STORAGE_ANALYTICS_PAGE_KEYS - discovered_keys)
    if missing:
        raise AssertionError('Object Storage Analytics Hero description authority missing for: ' + ', '.join(missing))
    return descriptions


def _materialization_route_descriptions() -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for path in sorted(KUBERNETES_ANALYTICS_ROUTES.rglob('routes.py')):
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(isinstance(target, ast.Name) and target.id == '_PAGE' for target in targets):
                continue
            value = node.value
            if not isinstance(value, ast.Dict):
                raise AssertionError(f'{path.relative_to(ROOT)}:{node.lineno}: _PAGE must remain a static dictionary')
            for key, item in zip(value.keys, value.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == 'description':
                    owner = f'materialization {path.relative_to(ROOT)}:{node.lineno}'
                    descriptions[owner] = _static_string(item, owner=owner)
    if not descriptions:
        raise AssertionError('Kubernetes Analytics materialization: no route-owned Hero descriptions discovered')
    return descriptions


def _effective_cluster_required_description(description: str) -> str:
    description = description.strip()
    if len(_description_words(description)) >= DESCRIPTION_MIN_WORDS:
        return description
    return f'{description.rstrip(".")} {CLUSTER_REQUIRED_CONTEXT_SUFFIX}'


def _cluster_required_descriptions() -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for path in sorted((ROOT / 'app').rglob('*.py')):
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            matched = (
                isinstance(function, ast.Name)
                and function.id == 'cluster_required'
                or isinstance(function, ast.Attribute)
                and function.attr == 'cluster_required'
            )
            if not matched:
                continue
            owner = f'{path.relative_to(ROOT)}:{node.lineno}'
            operation_node = (
                node.args[0]
                if node.args
                else next(
                    (keyword.value for keyword in node.keywords if keyword.arg == 'operation_label'),
                    None,
                )
            )
            operation = _static_string(operation_node, owner=owner)
            description_node = next(
                (keyword.value for keyword in node.keywords if keyword.arg == 'page_description'),
                None,
            )
            if description_node is None or (
                isinstance(description_node, ast.Constant) and description_node.value is None
            ):
                description = f'{operation} requires a registered Kubernetes cluster and canonical connection.'
            else:
                description = _static_string(description_node, owner=owner)
            descriptions[f'cluster_required {owner}'] = _effective_cluster_required_description(description)
    return descriptions


def _verify_description_budgets(primitive_shells: list[Path], profile_templates: list[Path]) -> int:
    descriptions = _literal_hero_descriptions(primitive_shells)
    descriptions.update(_dashboard_descriptions(profile_templates))
    descriptions.update(_provider_component_descriptions())
    descriptions.update(_integration_overview_descriptions())
    descriptions.update(_integration_domain_descriptions())
    descriptions.update(_reports_unavailable_descriptions())
    descriptions.update(_reports_page_subtitle_descriptions())
    descriptions.update(_object_storage_analytics_descriptions())
    descriptions.update(_materialization_route_descriptions())
    descriptions.update(_cluster_required_descriptions())
    failures: list[str] = []
    for owner, description in descriptions.items():
        try:
            _validate_description_budget(description, owner=owner)
        except AssertionError as exc:
            failures.append(str(exc))
    if failures:
        raise AssertionError('Hero description budget violations:\n- ' + '\n- '.join(failures))
    return len(descriptions)


def _verify_primitive_shell(path: Path) -> None:
    source = _read(path)
    relative = path.relative_to(ROOT)
    _require_tokens(
        source,
        (
            'import "components/page_hero.html" as page_hero',
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.content_classes()',
            'page_hero.intro(',
            'page_hero.title_classes()',
            'page_hero.description_classes()',
        ),
        str(relative),
    )
    if 'text-[13px]' in source or 'text-[15px]' in source:
        raise AssertionError(f'{relative}: arbitrary Hero typography is prohibited')
    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in source:
            raise AssertionError(f'{relative}: references removed Hero macro {macro}()')


def _verify_blocked_context_ownership() -> None:
    wrappers = (
        TEMPLATES / 'components' / 'cluster' / '_hero_blocked_context.html',
        TEMPLATES / 'storage' / 'object_storage' / 'inventory' / 'components' / '_hero_blocked_context.html',
        TEMPLATES / 'kubernetes' / 'analytics' / 'components' / '_blocked_posture.html',
        TEMPLATES / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero_blocked_posture.html',
    )
    for path in wrappers:
        source = _read(path)
        relative = path.relative_to(ROOT)
        if 'page_hero.blocked_context_body(' not in source:
            raise AssertionError(f'{relative}: blocked Hero must use blocked_context_body()')
        if 'page_hero.context_panel_classes()' in source:
            raise AssertionError(f'{relative}: blocked wrapper must not own context geometry')


def _verify_analytics_metadata_ownership() -> None:
    for path in (*KUBERNETES_ANALYTICS_HEROES, OBJECT_STORAGE_ANALYTICS_HERO):
        source = _read(path)
        relative = path.relative_to(ROOT)
        if 'page_hero.analytics_metadata(' not in source:
            raise AssertionError(f'{relative}: Analytics Hero must use analytics_metadata()')
        if 'page_hero.metadata_row_classes()' in source:
            raise AssertionError(f'{relative}: Analytics Hero must not own metadata geometry')
    object_storage = _read(OBJECT_STORAGE_ANALYTICS_HERO)
    expected = r"evidence_label\s*=\s*['\"]Committed Snapshot Boundary['\"]"
    if not re.search(expected, object_storage):
        raise AssertionError('Object Storage Analytics evidence label must be Committed Snapshot Boundary')
    if '{% if inventory_observed_at %}' in object_storage:
        raise AssertionError('Object Storage Analytics metadata must not depend on observation time')


def _verify_operational_metadata_state_contract() -> None:
    hero = _read(HERO)
    _require_tokens(
        hero,
        (
            'macro persistent_metadata(',
            'data-kaori-hero-metadata',
            'data-kaori-hero-metadata-policy="persistent"',
            'persistent_metadata(metadata)',
            'persistent_metadata(analytics_items)',
        ),
        'Hero persistent metadata renderer',
    )
    for path in (*KUBERNETES_ANALYTICS_HEROES, OBJECT_STORAGE_ANALYTICS_HERO):
        source = _read(path)
        relative = path.relative_to(ROOT)
        if 'page_hero.analytics_metadata(' not in source:
            raise AssertionError(f'{relative}: Analytics metadata must use persistent renderer')
        blocker_start = source.find('{% if dependency_blocker %}')
        if blocker_start < 0:
            continue
        blocker_end = source.find('{% endif %}', blocker_start)
        metadata_call = source.find('page_hero.analytics_metadata(')
        if blocker_end >= 0 and 0 <= metadata_call < blocker_end:
            raise AssertionError(f'{relative}: blocked readiness must be additive to metadata')

    blocked = _read(KUBERNETES_ANALYTICS_BLOCKED_HERO)
    _require_tokens(
        blocked,
        ('page_hero.analytics_metadata(', 'materialization_metadata'),
        'Generic Kubernetes Analytics blocked Hero',
    )
    presentation = _read(KUBERNETES_ANALYTICS_MATERIALIZATION_PRESENTATION)
    _require_tokens(
        presentation,
        (
            "'materialization_metadata': {",
            "'No Cluster Selected'",
            "'Blocked Readiness'",
        ),
        'Generic Kubernetes Analytics blocked metadata context',
    )


def _verify_dashboard_profile() -> None:
    dashboards = (
        TEMPLATES / 'kubernetes' / 'dashboard' / 'partials' / '_hero.html',
        TEMPLATES / 'storage' / 'object_storage' / 'dashboard' / 'partials' / '_hero.html',
    )
    for path in dashboards:
        source = _read(path)
        relative = path.relative_to(ROOT)
        _require_tokens(
            source,
            ('page_hero.operational_dashboard(', "'Committed Snapshots'"),
            str(relative),
        )
        for local in (
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.context_panel_classes()',
        ):
            if local in source:
                raise AssertionError(f'{relative}: dashboard profile must not assemble {local}')


def verify() -> None:
    hero = _read(HERO)
    standard = _read(STANDARD)
    dark_standard = _read(DARK_STANDARD)
    analytics_standard = _read(ANALYTICS_STANDARD)
    dashboard_standard = _read(DASHBOARD_STANDARD)

    implementation_tokens = (
        'min-h-[15.5rem]',
        'lg:min-h-[17.5rem]',
        'xl:grid-cols-12',
        'xl:col-span-7',
        'xl:col-span-5',
        'kaori-hero-shell',
        'kaori-hero-panel',
        'metrics[:2]',
        'metadata[:3]',
        'data-kaori-hero-profile="operational-dashboard"',
        'data-kaori-hero-state="{{ state }}"',
        'data-kaori-hero-metadata-policy="persistent"',
        'data-kaori-analytics-metadata',
        'text-3xl font-bold leading-10',
        'max-w-[44rem] text-base font-normal leading-7',
        'grid grid-cols-2 auto-rows-fr gap-2',
    )
    _require_tokens(hero, implementation_tokens, 'page_hero implementation')

    macros = _macro_names(hero)
    missing_macros = sorted(set(REQUIRED_MACROS) - macros)
    if missing_macros:
        raise AssertionError('page_hero implementation: missing macros: ' + ', '.join(missing_macros))
    present_removed = sorted(set(REMOVED_MACROS) & macros)
    if present_removed:
        raise AssertionError('page_hero implementation: removed macros exist: ' + ', '.join(present_removed))

    _require_tokens(
        standard,
        (
            '# KAORI Hero Component Standard v1.7',
            'Hero Profile',
            'Hero State',
            'same Profile + same State',
            'exactly three metadata',
            'normal, blocked, and degraded',
            '248 px / 280 px minimum',
            '16 px, regular, 28 px line height',
            'Action Icon Box',
            'Context Icon Box',
            'Status Badge Box',
            'exactly two compact metrics',
            'Blocked readiness grammar',
            'Missing Evidence',
            'blocked_context_body(...)',
            'components/ANALYTICS_HERO.md',
            '## Theme and surface contract',
            'components/DARK_MODE.md',
            'The canonical verifier enforces the 7–15 word boundary',
            'preferably 8–12 words',
            'maximum 110 characters',
            'action-oriented',
            'Integration domain descriptions are audited from',
            '## Change procedure',
        ),
        'Hero standard documentation',
    )
    _require_tokens(
        dark_standard,
        ('# KAORI Dark Mode Standard v1.0', 'kaori-hero-shell'),
        'Dark-mode Hero contract',
    )
    _require_tokens(
        analytics_standard,
        (
            '# Kubernetes Analytics Hero Extension',
            'Blocked Analytics metadata remains exactly three items',
            'page_hero.analytics_metadata(...)',
        ),
        'Analytics Hero extension',
    )
    _require_tokens(
        dashboard_standard,
        ('KAORI Operational Dashboard Pattern', 'Operational Dashboard Hero Profile'),
        'Operational Dashboard pattern',
    )

    primitive_shells = _primitive_shell_templates()
    if not primitive_shells:
        raise AssertionError('No compatibility Hero shell templates discovered')
    for path in primitive_shells:
        _verify_primitive_shell(path)

    profile_templates = _profile_templates()
    if len(profile_templates) != 2:
        raise AssertionError(
            f'Operational Dashboard profile must have exactly two consumers; found {len(profile_templates)}'
        )

    _verify_dashboard_profile()
    _verify_blocked_context_ownership()
    _verify_analytics_metadata_ownership()
    _verify_operational_metadata_state_contract()

    active_templates = '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATES.rglob('*.html') if path != HERO)
    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in active_templates:
            raise AssertionError(f'Active templates reference removed macro {macro}()')

    unmanaged: list[str] = []
    for path in TEMPLATES.rglob('*.html'):
        if path == HERO:
            continue
        if _has_unmanaged_hero_shell(_read(path)):
            unmanaged.append(str(path.relative_to(ROOT)))
    if unmanaged:
        raise AssertionError('Unmanaged Hero-like shell detected: ' + ', '.join(unmanaged))

    if 'python scripts/verify_hero_component_standard.py' not in _read(QUALITY_GATE):
        raise AssertionError('quality_gate.sh does not run Hero standard verifier')

    audited = _verify_description_budgets(primitive_shells, profile_templates)
    print(
        'KAORI Hero component standard passed: '
        f'{len(primitive_shells)} compatibility shells, '
        f'{len(profile_templates)} profile consumers, '
        f'{audited} audited descriptions; v1.7 persistent metadata, '
        '7-15 word density with a preferred 8-12 word range, maximum 110 characters, action-oriented copy, blocked/degraded state ownership, dynamic Jinja resolution, '
        'dark-mode ownership, and unmanaged-shell detection are synchronized.'
    )


if __name__ == '__main__':
    verify()
