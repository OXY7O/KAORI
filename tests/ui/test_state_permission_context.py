from pathlib import Path

from jinja2 import Environment, FileSystemLoader


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "app" / "templates"


def _environment() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATE_ROOT)), autoescape=True)


def test_empty_state_renders_without_current_user() -> None:
    template = _environment().from_string(
        """
        {% set empty_state_permission = 'clusters.manage' %}
        {% set empty_state_action_url = '/clusters/new' %}
        {% set empty_state_action_label = 'Add Cluster' %}
        {% set empty_state_show_admin_required = true %}
        {% include 'components/states/_empty_state.html' %}
        """
    )

    rendered = template.render()

    assert "Admin Required" in rendered
    assert "Add Cluster" not in rendered


def test_empty_state_accepts_explicit_permission_result() -> None:
    template = _environment().from_string(
        """
        {% set empty_state_permission = 'clusters.manage' %}
        {% set empty_state_permission_granted = true %}
        {% set empty_state_action_url = '/clusters/new' %}
        {% set empty_state_action_label = 'Add Cluster' %}
        {% include 'components/states/_empty_state.html' %}
        """
    )

    rendered = template.render()

    assert "Add Cluster" in rendered


def test_blocked_state_renders_without_current_user() -> None:
    template = _environment().from_string(
        """
        {% set blocked_state_permission = 'clusters.manage' %}
        {% set blocked_state_action_url = '/clusters/new' %}
        {% set blocked_state_action_label = 'Add Cluster' %}
        {% set blocked_state_show_admin_required = true %}
        {% include 'components/states/_blocked_state.html' %}
        """
    )

    rendered = template.render()

    assert "Admin Required" in rendered
    assert "Add Cluster" not in rendered
