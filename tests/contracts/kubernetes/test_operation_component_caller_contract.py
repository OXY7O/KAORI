from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


TEMPLATE_ROOT = Path(__file__).resolve().parents[3] / "app" / "templates"


@pytest.mark.parametrize("domain", ["configmaps", "secrets"])
def test_operation_action_bar_wrapper_forwards_call_block(domain: str) -> None:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.from_string(
        """
        {% import "kubernetes_operations/DOMAIN/_components.html" as operation_ui %}
        {% call operation_ui.action_bar(
            'scan-search',
            'Validate Before Creation',
            'Validate the manifest before applying it.'
        ) %}
            <button type="button">Validate</button>
            <button type="submit">Create</button>
        {% endcall %}
        """.replace("DOMAIN", domain)
    )

    rendered = template.render()

    assert "Validate Before Creation" in rendered
    assert '<button type="button">Validate</button>' in rendered
    assert '<button type="submit">Create</button>' in rendered
