from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "frontend" / "styles.css"
COMPILED = ROOT / "app" / "static" / "css" / "output.css"
STANDARD = ROOT / "docs" / "design" / "components" / "DARK_MODE.md"
DESIGN_SYSTEM = ROOT / "docs" / "design" / "KAORI_DESIGN_SYSTEM.md"
QUALITY_GATE = ROOT / "scripts" / "quality_gate.sh"
LAYOUT = ROOT / "app" / "templates" / "layouts" / "app.html"
NAVBAR = ROOT / "app" / "templates" / "components" / "navigation" / "navbar.html"
SIDEBAR = ROOT / "app" / "templates" / "components" / "navigation" / "sidebar.html"
HERO = ROOT / "app" / "templates" / "components" / "page_hero.html"
WELCOME_GROUP = ROOT / "app" / "templates" / "components" / "welcome_capability_group.html"
WORKSPACE_CARD = ROOT / "app" / "templates" / "components" / "workspace_link_card.html"
OBSOLETE_TOPBAR = ROOT / "app" / "templates" / "components" / "navigation" / "topbar.html"

DARK_TOKEN_VALUES = {
    "--kaori-surface-page": "#0f0d15",
    "--kaori-surface-sunken": "#121019",
    "--kaori-surface-shell": "#15121d",
    "--kaori-surface-sidebar": "#171321",
    "--kaori-surface-card": "#1d1925",
    "--kaori-surface-muted": "#201b2a",
    "--kaori-surface-elevated": "#25202f",
    "--kaori-surface-hover": "#282231",
    "--kaori-content-primary": "#f5f3f7",
    "--kaori-content-secondary": "#cbc5d2",
    "--kaori-content-muted": "#9d95a7",
    "--kaori-content-disabled": "#706878",
    "--kaori-outline-subtle": "#2b2535",
    "--kaori-outline-default": "#373043",
    "--kaori-outline-strong": "#4b4258",
}

STYLE_TOKENS = (
    "--kaori-hero-background:",
    "linear-gradient(120deg, #3b176e 0%, #4c1d95 52%, #32135d 100%)",
    "--kaori-hero-panel: rgba(15, 10, 24, 0.32)",
    "--kaori-sidebar-active: rgba(139, 92, 246, 0.18)",
    "--color-surface-shell: var(--kaori-surface-shell)",
    ".kaori-app-shell",
    ".kaori-hero-shell",
    ".kaori-hero-panel",
    ".kaori-hero-tile",
    ".kaori-hero-chip",
    ".kaori-brand-domain-panel",
    ".sidebar-parent-active",
    ".sidebar-parent-active-icon",
    ".sidebar-item-idle",
    ".sidebar-item-idle-icon",
    ".sidebar-section-label",
    ".dark .sidebar-parent-active",
    "box-shadow: inset 3px 0 0 var(--kaori-brand-primary)",
)

DOC_TOKENS = (
    "# KAORI Dark Mode Standard v1.0",
    "Neutral-first dark mode with controlled KAORI Violet",
    "80% neutral operational surfaces",
    "surface-shell",
    "#0F0D15",
    "#15121D",
    "#1D1925",
    "#25202F",
    "sidebar-parent-active",
    "kaori-hero-shell",
    "The only approved exception is the canonical dark Hero gradient",
    "scripts/verify_dark_mode_standard.py",
)


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"Missing required dark-mode file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _require_tokens(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f"{owner}: missing canonical tokens: {', '.join(missing)}")


def _dark_block(styles: str) -> str:
    match = re.search(r"\.dark\s*\{(?P<body>[\s\S]*?)\n\}", styles)
    if match is None:
        raise AssertionError("frontend/styles.css: missing canonical .dark token block")
    return match.group("body")



def _relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    high, low = sorted((_relative_luminance(foreground), _relative_luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _verify_contrast() -> None:
    checks = (
        ("primary on page", "#f5f3f7", "#0f0d15", 4.5),
        ("secondary on page", "#cbc5d2", "#0f0d15", 4.5),
        ("muted on page", "#9d95a7", "#0f0d15", 4.5),
        ("primary on card", "#f5f3f7", "#1d1925", 4.5),
        ("muted on card", "#9d95a7", "#1d1925", 4.5),
        ("sidebar muted on sidebar", "#b9b1c4", "#171321", 4.5),
    )
    failures = []
    for label, foreground, background, minimum in checks:
        ratio = _contrast_ratio(foreground, background)
        if ratio < minimum:
            failures.append(f"{label}: {ratio:.2f}:1 < {minimum:.1f}:1")
    if failures:
        raise AssertionError("Dark-mode contrast contract failed: " + "; ".join(failures))

def verify() -> None:
    styles = _read(STYLES)
    compiled = _read(COMPILED)
    standard = _read(STANDARD)
    design_system = _read(DESIGN_SYSTEM)
    quality_gate = _read(QUALITY_GATE)
    layout = _read(LAYOUT)
    navbar = _read(NAVBAR)
    sidebar = _read(SIDEBAR)
    hero = _read(HERO)
    welcome_group = _read(WELCOME_GROUP)
    workspace_card = _read(WORKSPACE_CARD)

    _require_tokens(styles, STYLE_TOKENS, "dark-mode token implementation")
    _verify_contrast()
    dark = _dark_block(styles)
    for token, value in DARK_TOKEN_VALUES.items():
        expected = f"{token}: {value};"
        if expected not in dark:
            raise AssertionError(f"frontend/styles.css: dark token drift for {token}; expected {value}")

    _require_tokens(standard, DOC_TOKENS, "dark-mode standard documentation")
    _require_tokens(
        design_system,
        (
            "neutral-first surfaces with controlled Violet",
            "surface-shell",
            "components/DARK_MODE.md",
            "canonical dark Hero gradient",
        ),
        "global design system",
    )

    _require_tokens(layout, ("kaori-app-shell", "bg-surface-shell"), "application frame")
    _require_tokens(navbar, ("kaori-app-shell", "bg-surface-shell"), "navbar")
    if "dark:bg-slate-" in navbar or "dark:text-slate-" in navbar:
        raise AssertionError("navbar: raw Slate dark-mode utilities are prohibited")

    _require_tokens(
        hero,
        ("kaori-hero-shell", "kaori-hero-panel", "kaori-hero-tile", "kaori-hero-chip"),
        "Hero shared component",
    )
    shell_macro = hero.split("{% macro layout_classes()", 1)[0]
    if "bg-kaori-primary" in shell_macro:
        raise AssertionError("Hero shell must not use the generic Bright Violet background utility")

    _require_tokens(
        sidebar,
        ("sidebar-parent-active", "sidebar-item-idle", "sidebar-section-label"),
        "sidebar shared frame",
    )
    navigation_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "app" / "templates" / "components" / "navigation").glob("*.html")
    )
    _require_tokens(
        navigation_source,
        ("sidebar-parent-active-icon", "sidebar-item-idle-icon"),
        "sidebar menu templates",
    )
    if "bg-kaori-primary text-white shadow-lg shadow-kaori-primary/20" in navigation_source:
        raise AssertionError("sidebar: legacy CTA-like active parent treatment remains")

    _require_tokens(welcome_group, ("kaori-brand-domain-panel",), "Welcome capability group")
    _require_tokens(workspace_card, ("kaori-workspace-card",), "Welcome workspace card")

    if OBSOLETE_TOPBAR.exists():
        raise AssertionError("Obsolete raw-Slate navigation/topbar.html still exists")

    _require_tokens(
        compiled,
        (
            "--kaori-surface-shell:#15121d",
            ".bg-surface-shell",
            ".kaori-hero-shell",
            ".sidebar-parent-active",
        ),
        "compiled CSS",
    )

    if "python scripts/verify_dark_mode_standard.py" not in quality_gate:
        raise AssertionError("scripts/quality_gate.sh does not execute the dark-mode verifier")

    print(
        "KAORI dark mode standard passed: neutral surface hierarchy, controlled Violet allocation, "
        "Hero/sidebar/application-shell ownership, compiled CSS, documentation, and dead-code cleanup "
        "match v1.0."
    )


if __name__ == "__main__":
    verify()
