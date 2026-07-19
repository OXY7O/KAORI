from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_product_wording_standard_exists():
    text = (ROOT / "docs/design/components/PRODUCT_WORDING.md").read_text()
    assert "Use **KAORI** whenever the subject or object is the product itself" in text
    assert "Do not mechanically replace words" in text


def test_known_generic_product_copy_does_not_return():
    targets = [
        ROOT / "app/templates/settings/general/partials/_time_locale.html",
        ROOT / "app/templates/settings/general/partials/_system_information.html",
        ROOT / "app/templates/settings/permissions/index.html",
        ROOT / "app/templates/errors/403.html",
        ROOT / "app/retention/presentation.py",
        ROOT / "app/notifications/normalization.py",
        ROOT / "app/alertmanager/routes.py",
    ]
    forbidden = (
        "opens the application",
        "this application version",
        "application access",
        "application logs",
        "available to the application",
    )
    combined = "\n".join(path.read_text() for path in targets)
    for phrase in forbidden:
        assert phrase not in combined
