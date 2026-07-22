from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"
TABLE_COMPONENT = TEMPLATES / "components" / "table.html"
TABLE_DOC = ROOT / "docs" / "design" / "components" / "TABLE_AND_LABEL.md"
AUDIT_DOC = ROOT / "docs" / "design" / "audits" / "TABLE_COMPONENT_AUDIT_2026_07.md"


def table_templates():
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "<table" in text.lower():
            yield path, text


def test_shared_table_component_exists_and_defines_core_contract():
    text = TABLE_COMPONENT.read_text(encoding="utf-8")
    for macro in (
        "block_header_classes",
        "loading_bar_classes",
        "filter_label_classes",
        "filter_input_classes",
        "filter_select_classes",
        "head_classes",
        "header_cell_classes",
        "cell_classes",
        "title_cell",
        "action_classes",
    ):
        assert f"macro {macro}" in text


def test_shared_table_component_uses_final_alignment_and_geometry():
    text = TABLE_COMPONENT.read_text(encoding="utf-8")
    assert "text-right' if action else 'text-left" in text
    assert "align-middle" in text
    assert "rounded-md" in text
    assert "hover:bg-kaori-soft" in text
    assert "cursor-pointer" in text
    assert "disabled:cursor-not-allowed" in text


def test_table_headers_do_not_force_uppercase_or_expanded_tracking():
    violations = []
    for path, text in table_templates():
        for tag in re.findall(r"<thead\b[^>]*>", text, flags=re.IGNORECASE):
            if re.search(r"\buppercase\b|\btracking-", tag):
                violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Legacy table header typography remains: {violations}"


def test_table_standard_documents_required_contracts():
    text = TABLE_DOC.read_text(encoding="utf-8")
    required = (
        "Loading bar",
        "Column alignment",
        "Table header typography",
        "Resource/title column",
        "Compact labels",
        "Table actions",
        "Filter bar",
        "Empty and error states",
        "Pagination",
        "Accessibility",
        "maximum: two words",
        "same application font family",
        "More than two are permitted",
        "Labels are also contextual rather than mandatory",
        "All ordinary non-CRUD table actions share one neutral utility appearance",
    )
    for phrase in required:
        assert phrase in text


def test_table_audit_report_exists_and_records_scope():
    text = AUDIT_DOC.read_text(encoding="utf-8")
    assert "53 template files" in text
    assert "57 table elements" in text
    assert "28 direct arbitrary table typography declarations" in text
    assert "19 table headers" in text



def test_table_headers_use_approved_size_and_semantic_color():
    violations = []
    for path, text in table_templates():
        for tag in re.findall(r"<thead\b[^>]*>", text, flags=re.IGNORECASE):
            if re.search(r"text-\[(?:10|11)px\]", tag) or "text-kaori-primary" in tag:
                violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Legacy table header size or color remains: {violations}"


def test_title_cell_scales_icon_for_two_line_content():
    text = TABLE_COMPONENT.read_text(encoding="utf-8")
    assert "'h-10 w-10' if supporting_text else 'h-8 w-8'" in text
    assert "'h-[18px] w-[18px]' if supporting_text else 'h-4 w-4'" in text
