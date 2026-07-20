from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

_LABEL_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_NUMBER_RE = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
_SUPPORTED_OPERATORS = {'=', '!=', '=~', '!~'}


class BindingSelectorError(ValueError):
    """Raised when a provider binding selector is invalid or conflicts with a query."""


@dataclass(frozen=True, slots=True)
class BindingMatcher:
    label: str
    operator: str
    value: str

    def as_filter(self) -> str:
        return f'{self.label}{self.operator}"{_escape_string(self.value)}"'


def build_selector(
    *,
    label: str | None,
    value: str | None,
    operator: str = '=',
) -> dict[str, Any] | None:
    normalized_label = str(label or '').strip()
    normalized_value = str(value or '').strip()
    normalized_operator = str(operator or '=').strip()

    if not normalized_label and not normalized_value:
        return None
    if not normalized_label or not normalized_value:
        raise BindingSelectorError('Both selector label and selector value are required.')
    if not _LABEL_RE.fullmatch(normalized_label):
        raise BindingSelectorError(
            'Selector label must start with a letter or underscore and contain only letters, numbers, or underscores.'
        )
    if normalized_operator not in _SUPPORTED_OPERATORS:
        raise BindingSelectorError('Selector operator is not supported.')
    if len(normalized_value) > 255:
        raise BindingSelectorError('Selector value must be 255 characters or fewer.')

    return {
        'matchers': [
            {
                'label': normalized_label,
                'operator': normalized_operator,
                'value': normalized_value,
            }
        ]
    }


def parse_matchers(selector_json: dict[str, Any] | None) -> tuple[BindingMatcher, ...]:
    if not isinstance(selector_json, dict):
        return ()
    raw_matchers = selector_json.get('matchers')
    if not isinstance(raw_matchers, list):
        return ()

    matchers: list[BindingMatcher] = []
    for item in raw_matchers:
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or '').strip()
        operator = str(item.get('operator') or '=').strip()
        value = str(item.get('value') or '').strip()
        if not label or not value or not _LABEL_RE.fullmatch(label) or operator not in _SUPPORTED_OPERATORS:
            continue
        matchers.append(BindingMatcher(label=label, operator=operator, value=value))
    return tuple(matchers)


def selector_filters(selector_json: dict[str, Any] | None) -> tuple[str, ...]:
    return tuple(matcher.as_filter() for matcher in parse_matchers(selector_json))


def selector_summary(selector_json: dict[str, Any] | None, *, empty: str = 'Unscoped') -> str:
    filters = selector_filters(selector_json)
    return ', '.join(filters) if filters else empty


def selector_is_configured(selector_json: dict[str, Any] | None) -> bool:
    return bool(parse_matchers(selector_json))


def selector_form_values(selector_json: dict[str, Any] | None) -> dict[str, str]:
    """Return the first canonical matcher in a form-friendly representation."""
    matchers = parse_matchers(selector_json)
    if not matchers:
        return {'label': '', 'operator': '=', 'value': ''}
    matcher = matchers[0]
    return {
        'label': matcher.label,
        'operator': matcher.operator,
        'value': matcher.value,
    }


def apply_promql_scope(expression: str, selector_json: dict[str, Any] | None) -> str:
    """Apply binding matchers to every vector selector in a PromQL expression.

    The implementation is deliberately lexical rather than regex-only: it keeps
    strings and comments intact, updates explicit ``{...}`` selectors, and adds a
    selector to bare metric identifiers while excluding functions, aggregation
    operators, durations, and label-list modifiers such as ``by(...)``/``on(...)``.
    """
    matchers = parse_matchers(selector_json)
    if not matchers:
        return expression
    scoped = _inject_explicit_selectors(expression, matchers)
    return _inject_bare_metric_selectors(scoped, matchers)


def _inject_explicit_selectors(expression: str, matchers: tuple[BindingMatcher, ...]) -> str:
    output: list[str] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == '"':
            end = _consume_string(expression, index)
            output.append(expression[index:end])
            index = end
            continue
        if char == '#':
            end = expression.find('\n', index)
            if end == -1:
                output.append(expression[index:])
                break
            output.append(expression[index:end])
            index = end
            continue
        if char != '{':
            output.append(char)
            index += 1
            continue

        end = _find_selector_end(expression, index)
        content = expression[index + 1:end - 1]
        additions = _missing_matchers(content, matchers)
        if additions:
            rendered = ','.join(matcher.as_filter() for matcher in additions)
            if content.strip():
                rendered = f'{rendered},{content}'
            output.append('{' + rendered + '}')
        else:
            output.append(expression[index:end])
        index = end
    return ''.join(output)


def _missing_matchers(content: str, matchers: tuple[BindingMatcher, ...]) -> tuple[BindingMatcher, ...]:
    configured_by_label = {matcher.label: matcher for matcher in matchers}
    existing: dict[str, tuple[str, str]] = {}
    pattern = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*(=~|!~|!=|=)\s*"((?:\\.|[^"\\])*)"')
    for match in pattern.finditer(content):
        existing[match.group(1)] = (match.group(2), _unescape_string(match.group(3)))

    missing: list[BindingMatcher] = []
    for label, matcher in configured_by_label.items():
        current = existing.get(label)
        if current is None:
            missing.append(matcher)
            continue
        if current != (matcher.operator, matcher.value):
            raise BindingSelectorError(
                f'PromQL already contains a conflicting matcher for binding label {label!r}.'
            )
    return tuple(missing)


def _inject_bare_metric_selectors(expression: str, matchers: tuple[BindingMatcher, ...]) -> str:
    tokens = _tokenize(expression)
    if not tokens:
        return expression

    label_list_ranges = _label_list_token_ranges(tokens)
    insertion = '{' + ','.join(matcher.as_filter() for matcher in matchers) + '}'
    reserved = {
        'and', 'or', 'unless', 'offset', 'bool', 'by', 'without', 'on', 'ignoring',
        'group_left', 'group_right', 'sum', 'min', 'max', 'avg', 'group', 'stddev',
        'stdvar', 'count', 'count_values', 'bottomk', 'topk', 'quantile', 'limitk',
        'limit_ratio', 'atan2', 'start', 'end', 'inf', 'nan',
    }
    insert_positions: list[int] = []
    brace_depth = 0
    for index, token in enumerate(tokens):
        value = token.value
        if value == '{':
            brace_depth += 1
            continue
        if value == '}':
            brace_depth = max(brace_depth - 1, 0)
            continue
        if token.kind != 'identifier' or brace_depth or index in label_list_ranges:
            continue
        lowered = value.lower()
        if lowered in reserved:
            continue
        next_token = _next_significant(tokens, index)
        previous_token = _previous_significant(tokens, index)
        if next_token and next_token.value in {'(', '{'}:
            continue
        if previous_token and previous_token.end == token.start and previous_token.kind in {'identifier', 'number'}:
            continue
        if previous_token and previous_token.value in {'.', '$'}:
            continue
        insert_positions.append(token.end)

    if not insert_positions:
        return expression
    output = expression
    for position in reversed(insert_positions):
        output = output[:position] + insertion + output[position:]
    return output


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    start: int
    end: int


def _tokenize(expression: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char == '"':
            end = _consume_string(expression, index)
            tokens.append(_Token('string', expression[index:end], index, end))
            index = end
            continue
        if char == '#':
            end = expression.find('\n', index)
            if end == -1:
                end = len(expression)
            tokens.append(_Token('comment', expression[index:end], index, end))
            index = end
            continue
        if char.isalpha() or char in {'_', ':'}:
            end = index + 1
            while end < len(expression) and (expression[end].isalnum() or expression[end] in {'_', ':'}):
                end += 1
            tokens.append(_Token('identifier', expression[index:end], index, end))
            index = end
            continue
        if char.isdigit() or (char == '.' and index + 1 < len(expression) and expression[index + 1].isdigit()):
            match = _NUMBER_RE.match(expression, index)
            if match is None:  # Defensive fallback; the branch guarantees a numeric prefix.
                end = index + 1
            else:
                end = match.end()
            tokens.append(_Token('number', expression[index:end], index, end))
            index = end
            continue
        two = expression[index:index + 2]
        if two in {'=~', '!~', '!=', '==', '>=', '<='}:
            tokens.append(_Token('symbol', two, index, index + 2))
            index += 2
            continue
        tokens.append(_Token('symbol', char, index, index + 1))
        index += 1
    return tokens


def _label_list_token_ranges(tokens: list[_Token]) -> set[int]:
    labels: set[int] = set()
    introducers = {'by', 'without', 'on', 'ignoring', 'group_left', 'group_right'}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == 'identifier' and token.value.lower() in introducers:
            open_index = index + 1
            while open_index < len(tokens) and tokens[open_index].kind == 'comment':
                open_index += 1
            if open_index < len(tokens) and tokens[open_index].value == '(':
                depth = 1
                cursor = open_index + 1
                while cursor < len(tokens) and depth:
                    if tokens[cursor].value == '(':
                        depth += 1
                    elif tokens[cursor].value == ')':
                        depth -= 1
                    elif depth and tokens[cursor].kind == 'identifier':
                        labels.add(cursor)
                    cursor += 1
                index = cursor
                continue
        index += 1
    return labels


def _next_significant(tokens: list[_Token], index: int) -> _Token | None:
    for token in tokens[index + 1:]:
        if token.kind != 'comment':
            return token
    return None


def _previous_significant(tokens: list[_Token], index: int) -> _Token | None:
    for token in reversed(tokens[:index]):
        if token.kind != 'comment':
            return token
    return None


def _consume_string(value: str, start: int) -> int:
    index = start + 1
    while index < len(value):
        if value[index] == '\\':
            index += 2
            continue
        if value[index] == '"':
            return index + 1
        index += 1
    raise BindingSelectorError('Unterminated string literal in PromQL expression.')


def _find_selector_end(value: str, start: int) -> int:
    index = start + 1
    while index < len(value):
        if value[index] == '"':
            index = _consume_string(value, index)
            continue
        if value[index] == '}':
            return index + 1
        index += 1
    raise BindingSelectorError('Unterminated label selector in PromQL expression.')


def _escape_string(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _unescape_string(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == '\\' and index + 1 < len(value):
            escaped = value[index + 1]
            result.append('\n' if escaped == 'n' else escaped)
            index += 2
            continue
        result.append(value[index])
        index += 1
    return ''.join(result)
