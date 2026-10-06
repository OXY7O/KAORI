from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORAGE_PATH = 'app/reports/export/html_pdf/storage_analysis.py'
BUILDER_PATH = 'app/reports/export/html_pdf/builder.py'


def _module(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding='utf-8'))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{name} was not found')


def _call(module: ast.Module, name: str) -> ast.Call:
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
            return node
    raise AssertionError(f'{name} call was not found')


def test_storage_analysis_uses_report_document_context_boundary() -> None:
    function = _function(_module(STORAGE_PATH), 'build_storage_analysis_presentation')
    positional = [argument.arg for argument in (*function.args.posonlyargs, *function.args.args)]
    keyword_only = [argument.arg for argument in function.args.kwonlyargs]

    assert positional == ['payload']
    assert keyword_only == ['context', 'classification']

    call = _call(_module(BUILDER_PATH), 'build_storage_analysis_presentation')
    assert len(call.args) == 1
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == 'payload'
    assert [keyword.arg for keyword in call.keywords] == ['context', 'classification']
