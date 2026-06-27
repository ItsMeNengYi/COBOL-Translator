"""Prompt and context helpers for unsupported COBOL rule translation."""

from __future__ import annotations

import json
import re
from typing import Any

MONEY_NAME_RE = re.compile(r"(BAL|BALANCE|AMOUNT|AMT|PRICE|TOTAL|PAY|SALARY|WAGE|FEE|COST)", re.IGNORECASE)


def _field_type(cobol_name: str, symbol_table: dict[str, Any], data_layout: dict[str, Any]) -> str | None:
    if MONEY_NAME_RE.search(str(cobol_name)):
        return "Decimal"
    for file_info in (data_layout.get("files") or {}).values():
        for field in file_info.get("fields") or []:
            if field.get("name") == cobol_name:
                return "Decimal" if MONEY_NAME_RE.search(str(field.get("name"))) else field.get("type")

    symbol = symbol_table.get(cobol_name)
    if not isinstance(symbol, dict):
        return None
    if symbol.get("scale", 0):
        return "Decimal"
    return symbol.get("python_type") or symbol.get("type")


def _variable_names_from_value(value: Any, symbol_table: dict[str, Any]) -> set[str]:
    if value is None:
        return set()
    text = str(value)
    found: set[str] = set()
    for name in symbol_table:
        if re.search(rf"\b{re.escape(name)}\b", text):
            found.add(name)
    return found


def _collect_rule_variables(value: Any, symbol_table: dict[str, Any]) -> set[str]:
    variables: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"source", "target", "left", "right", "subject", "record"}:
                variables.update(_variable_names_from_value(nested, symbol_table))
            elif key in {"expression", "value"}:
                variables.update(_variable_names_from_value(nested, symbol_table))
            else:
                variables.update(_collect_rule_variables(nested, symbol_table))
    elif isinstance(value, list):
        for item in value:
            variables.update(_collect_rule_variables(item, symbol_table))
    else:
        variables.update(_variable_names_from_value(value, symbol_table))
    return variables


def _relevant_file_layout(rule: dict[str, Any], data_layout: dict[str, Any]) -> dict[str, Any]:
    file_name = rule.get("file")
    record_name = rule.get("record")
    relevant: dict[str, Any] = {}

    for candidate_name, file_info in (data_layout.get("files") or {}).items():
        if candidate_name == file_name or file_info.get("record_name") == record_name:
            relevant[candidate_name] = file_info
    return relevant


def build_translation_context(
    rule: dict[str, Any],
    symbol_table: dict[str, Any],
    control_flow: dict[str, Any],
    data_layout: dict[str, Any],
) -> dict[str, Any]:
    """Build the smallest useful LLM context for one unsupported rule."""
    variable_names = _collect_rule_variables(rule, symbol_table)
    file_layout = _relevant_file_layout(rule, data_layout)

    for file_info in file_layout.values():
        for field in file_info.get("fields") or []:
            name = field.get("name")
            if name:
                variable_names.add(str(name))

    variables = {
        name: {
            "python_name": symbol_table.get(name, {}).get("python_name"),
            "type": _field_type(name, symbol_table, data_layout),
            "pic": symbol_table.get(name, {}).get("pic"),
            "scale": symbol_table.get(name, {}).get("scale"),
            "is_decimal": _field_type(name, symbol_table, data_layout) == "Decimal",
        }
        for name in sorted(variable_names)
        if isinstance(symbol_table.get(name), dict)
    }

    paragraph = rule.get("paragraph")
    paragraph_flow = {
        "entry_point": control_flow.get("entry_point"),
        "edges": [
            edge for edge in control_flow.get("edges", [])
            if edge.get("from") == paragraph or edge.get("to") == paragraph
        ],
        "loops": [
            loop for loop in control_flow.get("loops", [])
            if loop.get("paragraph") == paragraph
        ],
    }

    return {
        "paragraph": paragraph,
        "rule": rule,
        "variables": variables,
        "symbol_table": {
            name: symbol_table[name]
            for name in variables
            if name in symbol_table
        },
        "control_flow": paragraph_flow,
        "file_layout": file_layout,
    }


def build_translation_prompt(context: dict[str, Any]) -> str:
    """Build the constrained translation prompt for a single unsupported rule."""
    symbol_table = json.dumps(context.get("symbol_table", {}), indent=2, sort_keys=True)
    control_flow = json.dumps(context.get("control_flow", {}), indent=2, sort_keys=True)
    rule_ir = json.dumps(context.get("rule", {}), indent=2, sort_keys=True)
    file_layout = json.dumps(context.get("file_layout", {}), indent=2, sort_keys=True)
    unsupported_block = json.dumps(context.get("unsupported_block", {}), indent=2, sort_keys=True)

    return f"""You are a COBOL semantic migration expert.

Translate exactly one unsupported COBOL semantic action into Python.

Rules:

1. Preserve COBOL behavior exactly.
2. Never invent business logic.
3. Use Decimal for money.
4. Preserve file semantics.
5. Preserve fixed-width strings.
6. Use the supplied Python variable names.
7. Return ONLY executable Python code.
8. Do not include markdown.
9. Do not rewrite other functions.
10. Return only the replacement for the supplied TODO line.
11. Do not include imports.
12. Do not define functions or classes.
13. Do not redeclare variables with type annotations.
14. Do not include global or nonlocal statements.
15. Use only variables and helpers already available in the generated function scope.

Variable definitions:
{symbol_table}

Control flow:
{control_flow}

File layout:
{file_layout}

Unsupported TODO block to replace:
{unsupported_block}

Rule:
{rule_ir}
"""
