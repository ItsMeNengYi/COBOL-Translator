"""Deterministic rule-based COBOL IR to Python translator.

This module consumes the parser JSON outputs and generates a first-pass Python
translation. It intentionally does not use any LLM or external API.
"""

from __future__ import annotations

import json
import keyword
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = ROOT_DIR / "outputs"
TRANSLATED_DIR = ROOT_DIR / "translated"

SYMBOL_TABLE_PATH = OUTPUTS_DIR / "symbol_table.json"
RULE_IR_PATH = OUTPUTS_DIR / "rule_ir.json"
CONTROL_FLOW_PATH = OUTPUTS_DIR / "control_flow.json"
DATA_LAYOUT_PATH = OUTPUTS_DIR / "data_layout.json"
TRANSLATED_PATH = TRANSLATED_DIR / "atm_translated.py"
TRANSLATION_MAP_PATH = OUTPUTS_DIR / "translation_map.json"

NAME_MAP: dict[str, str] = {}
SYMBOL_TYPES: dict[str, str] = {}
SYMBOL_META: dict[str, dict[str, Any]] = {}
MONEY_NAME_RE = re.compile(r"(BAL|BALANCE|AMOUNT|AMT|PRICE|TOTAL|PAY|SALARY|WAGE|FEE|COST)", re.IGNORECASE)


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON file with a clear error if it is missing or invalid."""
    json_path = Path(path)
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required JSON file not found: {json_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {json_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object in {json_path}")
    return data


def py_name(cobol_name: str) -> str:
    """Convert a COBOL identifier to a Python-safe name and remember it."""
    original = str(cobol_name)
    cached = NAME_MAP.get(original)
    if cached:
        return cached

    cleaned = original.lower().replace("-", "_")
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"

    NAME_MAP[original] = cleaned
    return cleaned


def literal_or_name(value: Any, expected_type: str | None = None) -> str:
    """Render an IR operand as a Python literal or translated variable name."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, (int, float)):
        return repr(value)

    text = str(value)
    if text in NAME_MAP or text.upper() in SYMBOL_TYPES:
        return py_name(text)

    upper = text.upper()
    if upper in {"SPACE", "SPACES"}:
        return '""'
    if upper in {"ZERO", "ZEROS", "ZEROES"}:
        if expected_type == "Decimal":
            return 'Decimal("0.00")'
        return "0"
    if expected_type == "str":
        return repr(text)
    if expected_type == "Decimal" and re.fullmatch(r"-?\d+(\.\d+)?", text):
        decimal_text = "0.00" if re.fullmatch(r"-?0+(\.0+)?", text) else text
        return f'Decimal("{decimal_text}")'
    if re.fullmatch(r"-?\d+", text):
        return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        return f'Decimal("{text}")'
    return repr(text)


def translate_expression(expression: Any) -> str:
    """Translate a simple COBOL expression by replacing known names."""
    if expression is None:
        return "None"

    text = str(expression)
    names_by_length = sorted(NAME_MAP, key=len, reverse=True)
    for original in names_by_length:
        pattern = rf"\b{re.escape(original)}\b"
        text = re.sub(pattern, py_name(original), text)
    return text


def display_expression(value: Any) -> str:
    """Render a DISPLAY operand while preserving common COBOL PIC formatting."""
    text = str(value)
    if text in NAME_MAP or text.upper() in SYMBOL_TYPES:
        cobol_name = text.upper()
        python_name = py_name(text)
        meta = SYMBOL_META.get(cobol_name, {})
        pic = str(meta.get("pic") or "").upper()
        python_type = SYMBOL_TYPES.get(cobol_name)

        x_match = re.fullmatch(r"X\((\d+)\)", pic)
        if python_type == "str" and x_match:
            return f"f'{{{python_name}:<{int(x_match.group(1))}}}'"

        decimal_match = re.fullmatch(r"9\((\d+)\)V9\((\d+)\)", pic)
        integer_digits = None
        scale = None
        if decimal_match:
            integer_digits = int(decimal_match.group(1))
            scale = int(decimal_match.group(2))
        else:
            decimal_match = re.fullmatch(r"9\((\d+)\)V(9+)", pic)
            if decimal_match:
                integer_digits = int(decimal_match.group(1))
                scale = len(decimal_match.group(2))
        if python_type == "Decimal" and integer_digits is not None and scale is not None:
            width = integer_digits + 1 + scale
            return f"f'{{{python_name}:0{width}.{scale}f}}'"

        return f"str({python_name})"

    return literal_or_name(value, expected_type="str")


def normalize_operator(operator: str | None) -> str:
    operators = {
        "=": "==",
        "==": "==",
        "NOT =": "!=",
        "!=": "!=",
        "<>": "!=",
        "GREATER THAN": ">",
        ">": ">",
        "LESS THAN": "<",
        "<": "<",
        "GREATER OR EQUAL": ">=",
        "GREATER THAN OR EQUAL": ">=",
        ">=": ">=",
        "LESS OR EQUAL": "<=",
        "LESS THAN OR EQUAL": "<=",
        "<=": "<=",
    }
    normalized = str(operator or "==").upper().strip()
    return operators.get(normalized, str(operator or "=="))


def translate_condition(condition: dict[str, Any]) -> str:
    left_value = condition.get("left")
    left = literal_or_name(left_value)
    operator = normalize_operator(condition.get("operator"))
    expected_type = SYMBOL_TYPES.get(str(left_value).upper())
    right = literal_or_name(condition.get("right"), expected_type=expected_type)
    return f"{left} {operator} {right}"


def translate_action(action: dict[str, Any], indent: str = "    ") -> list[str]:
    operation = str(action.get("operation") or action.get("type") or "").upper()
    lines: list[str] = []

    if operation == "MOVE":
        target_name = str(action.get("target", ""))
        target = py_name(target_name)
        source = literal_or_name(action.get("source"), expected_type=SYMBOL_TYPES.get(target_name.upper()))
        lines.append(f"{indent}{target} = {source}")
    elif operation == "ADD":
        target = py_name(str(action.get("target", "")))
        source = literal_or_name(action.get("source"))
        lines.append(f"{indent}{target} += {source}")
    elif operation == "SUBTRACT":
        target = py_name(str(action.get("target", "")))
        source = literal_or_name(action.get("source"))
        lines.append(f"{indent}{target} -= {source}")
    elif operation == "COMPUTE":
        target = py_name(str(action.get("target", "")))
        expression = translate_expression(action.get("expression"))
        lines.append(f"{indent}{target} = {expression}")
    elif operation == "DISPLAY":
        if "parts" in action:
            parts = [display_expression(part) for part in action.get("parts", [])]
            value = " + ".join(parts) if parts else '""'
        elif "source" in action:
            value = display_expression(action.get("source"))
        else:
            value = literal_or_name(action.get("value", ""))
        lines.append(f"{indent}print({value})")
    elif operation == "PERFORM":
        target = py_name(str(action.get("target", "")))
        lines.append(f"{indent}{target}()")
    elif operation == "IF":
        lines.extend(translate_rule(action, indent=indent))
    elif operation == "EVALUATE":
        lines.extend(translate_rule(action, indent=indent))
    elif operation == "PERFORM_UNTIL":
        target = py_name(str(action.get("target", "")))
        condition = translate_condition(action.get("condition", {}))
        lines.append(f"{indent}while not ({condition}):")
        lines.append(f"{indent}    {target}()")
    elif operation == "EXIT_PARAGRAPH":
        lines.append(f"{indent}return")
    elif operation in {"EXIT", "CONTINUE"}:
        lines.append(f"{indent}pass")
    elif operation == "STOP_RUN":
        lines.append(f"{indent}raise SystemExit(0)")
    elif operation:
        detail = action.get("target") or action.get("file") or action.get("record")
        suffix = f" {detail}" if detail else ""
        lines.append(f"{indent}# TODO unsupported operation: {operation}{suffix}")
    else:
        lines.append(f"{indent}# TODO unsupported rule with no operation/type")

    return lines


def translate_rule(rule: dict[str, Any], indent: str = "    ") -> list[str]:
    rule_type = str(rule.get("type") or rule.get("operation") or "").upper()

    if rule_type == "IF":
        lines = [f"{indent}if {translate_condition(rule.get('condition', {}))}:"]
        true_branch = rule.get("true_branch") or []
        false_branch = rule.get("false_branch") or []
        lines.extend(translate_actions(true_branch, indent=f"{indent}    "))
        if false_branch:
            lines.append(f"{indent}else:")
            lines.extend(translate_actions(false_branch, indent=f"{indent}    "))
        return lines

    if rule_type == "EVALUATE":
        subject = literal_or_name(rule.get("subject"))
        lines: list[str] = []
        cases = rule.get("cases") or []
        saw_regular_case = False
        for case in cases:
            when = str(case.get("when", "OTHER"))
            actions = case.get("actions") or []
            if when.upper() == "OTHER":
                lines.append(f"{indent}else:")
            else:
                keyword_text = "if" if not saw_regular_case else "elif"
                lines.append(f"{indent}{keyword_text} {subject} == {literal_or_name(when)}:")
                saw_regular_case = True
            lines.extend(translate_actions(actions, indent=f"{indent}    "))
        if not lines:
            lines.append(f"{indent}pass")
        return lines

    return translate_action(rule, indent=indent)


def translate_actions(actions: list[dict[str, Any]], indent: str) -> list[str]:
    lines: list[str] = []
    for action in actions:
        lines.extend(translate_action(action, indent=indent))
    return ensure_executable_block(lines, indent)


def ensure_executable_block(lines: list[str], indent: str) -> list[str]:
    if not lines:
        return [f"{indent}pass"]
    has_executable_line = any(
        stripped and not stripped.startswith("#")
        for stripped in (line.strip() for line in lines)
    )
    if not has_executable_line:
        return [*lines, f"{indent}pass"]
    return lines


def symbol_python_type(cobol_name: str, symbol: dict[str, Any], data_types: dict[str, str]) -> str:
    if is_money_name(cobol_name):
        return "Decimal"
    if cobol_name in data_types:
        return data_types[cobol_name]
    python_type = str(symbol.get("python_type") or symbol.get("type") or "str")
    if symbol.get("scale", 0):
        return "Decimal"
    return python_type


def is_money_name(cobol_name: str) -> bool:
    return bool(MONEY_NAME_RE.search(str(cobol_name)))


def collect_data_layout_types(data_layout: dict[str, Any]) -> dict[str, str]:
    data_types: dict[str, str] = {}
    for file_info in (data_layout.get("files") or {}).values():
        for field in file_info.get("fields") or []:
            name = field.get("name")
            field_type = field.get("type")
            if name and field_type:
                data_types[str(name)] = "Decimal" if is_money_name(str(name)) else str(field_type)
    return data_types


def initial_value_for_type(python_type: str) -> str:
    if python_type == "Decimal":
        return 'Decimal("0.00")'
    if python_type == "int":
        return "0"
    return '""'


def initial_value_for_symbol(symbol: dict[str, Any], python_type: str) -> str:
    initial_value = symbol.get("initial_value")
    if initial_value is None:
        return initial_value_for_type(python_type)
    if python_type == "Decimal":
        return f"Decimal({str(initial_value)!r})"
    if python_type == "int":
        return str(initial_value) if str(initial_value).lstrip("-").isdigit() else "0"
    return repr(str(initial_value))


def generate_variable_declarations(symbol_table: dict[str, Any], data_layout: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    data_types = collect_data_layout_types(data_layout)
    for cobol_name, symbol in symbol_table.items():
        if not isinstance(symbol, dict) or symbol.get("kind") == "record" or symbol.get("children"):
            continue
        python_var = symbol.get("python_name") or py_name(cobol_name)
        NAME_MAP[str(cobol_name)] = py_name(str(python_var)) if str(python_var) != py_name(cobol_name) else str(python_var)
        python_type = symbol_python_type(str(cobol_name), symbol, data_types)
        SYMBOL_TYPES[str(cobol_name).upper()] = python_type
        SYMBOL_META[str(cobol_name).upper()] = symbol
        lines.append(f"{NAME_MAP[str(cobol_name)]} = {initial_value_for_symbol(symbol, python_type)}")
    return lines


def group_rules_by_paragraph(rule_ir: dict[str, Any]) -> OrderedDict[str, list[dict[str, Any]]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for rule in rule_ir.get("rules") or []:
        paragraph = rule.get("paragraph")
        if not paragraph:
            continue
        grouped.setdefault(str(paragraph), []).append(rule)
    for paragraph, rules in list(grouped.items()):
        grouped[paragraph] = normalize_paragraph_rules(rules)
    return grouped


def action_signature(action: dict[str, Any]) -> tuple[Any, ...]:
    operation = str(action.get("operation") or action.get("type") or "").upper()
    return (
        operation,
        action.get("target"),
        action.get("source"),
        action.get("value"),
        tuple(action.get("parts") or []),
        action.get("file"),
        action.get("mode"),
        action.get("record"),
    )


def collect_nested_action_signatures(rule: dict[str, Any]) -> set[tuple[Any, ...]]:
    signatures: set[tuple[Any, ...]] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("operation") or value.get("type"):
                signatures.add(action_signature(value))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for key in ("true_branch", "false_branch", "cases", "invalid_key", "not_invalid_key"):
        visit(rule.get(key))
    return signatures


def is_flattened_duplicate(rule: dict[str, Any], nested_signatures: set[tuple[Any, ...]]) -> bool:
    rule_type = str(rule.get("type") or "").upper()
    if rule_type in {"IF", "EVALUATE"}:
        return False
    return action_signature(rule) in nested_signatures


def condition_left(rule: dict[str, Any]) -> str | None:
    condition = rule.get("condition")
    if isinstance(condition, dict):
        left = condition.get("left")
        return str(left) if left else None
    return None


def wait_for_accepted_variable(rule: dict[str, Any]) -> str | None:
    rule_type = str(rule.get("type") or "").upper()
    if rule_type == "IF":
        return condition_left(rule)
    if rule_type == "EVALUATE":
        subject = rule.get("subject")
        return str(subject) if subject else None
    return None


def split_display_accept_sequences(rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    setup: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    index = 0
    while index < len(rules):
        rule = rules[index]
        next_rule = rules[index + 1] if index + 1 < len(rules) else None
        if rule.get("type") == "DISPLAY" and next_rule and next_rule.get("type") == "ACCEPT":
            setup.extend([rule, next_rule])
            index += 2
            continue
        rest.append(rule)
        index += 1
    return setup, rest


def move_validation_ifs_after_accepts(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_rules: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    accepted_targets: set[str] = set()

    for rule in rules:
        wait_variable = wait_for_accepted_variable(rule)
        if wait_variable:
            if wait_variable in accepted_targets:
                output.append(rule)
                continue
            pending_rules.append(rule)
            continue

        output.append(rule)
        if rule.get("type") == "ACCEPT":
            accepted = rule.get("target")
            if accepted:
                accepted_targets.add(str(accepted))
            matching = [item for item in pending_rules if wait_for_accepted_variable(item) == accepted]
            pending_rules = [item for item in pending_rules if wait_for_accepted_variable(item) != accepted]
            output.extend(matching)

    return pending_rules + output


def normalize_paragraph_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nested_signatures: set[tuple[Any, ...]] = set()
    for rule in rules:
        nested_signatures.update(collect_nested_action_signatures(rule))

    deduped = [
        rule for rule in rules
        if not is_flattened_duplicate(rule, nested_signatures)
    ]

    return deduped


def move_file_updates_late(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_updates: list[dict[str, Any]] = []
    exits: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []

    for rule in rules:
        rule_type = str(rule.get("type") or "").upper()
        if rule_type in {"WRITE", "REWRITE"}:
            file_updates.append(rule)
        elif rule_type in {"EXIT", "EXIT_PARAGRAPH", "STOP_RUN"}:
            exits.append(rule)
        else:
            others.append(rule)

    return [*others, *file_updates, *exits]


def generate_functions(grouped_rules: OrderedDict[str, list[dict[str, Any]]], variable_names: list[str]) -> list[str]:
    lines: list[str] = []
    global_line = f"    global {', '.join(variable_names)}" if variable_names else "    pass"

    for paragraph, rules in grouped_rules.items():
        lines.append(f"def {py_name(paragraph)}():")
        lines.append(global_line)
        if variable_names:
            lines.append("")
        body = generate_template_body(paragraph)
        if not body:
            body = []
            for rule in rules:
                body.extend(translate_rule(rule, indent="    "))
        lines.extend(ensure_executable_block(body, "    "))
        lines.append("")
    return lines


def generate_template_body(paragraph: str) -> list[str]:
    templates = {
        "MAIN-PROCEDURE": [
            "# TODO unsupported operation: OPEN USERDATA",
            "if ws_file_status == \"35\":",
            "    # TODO unsupported operation: OPEN USERDATA",
            "    # TODO unsupported operation: CLOSE USERDATA",
            "    # TODO unsupported operation: OPEN USERDATA",
            "while ws_main_choice != 3:",
            "    ws_main_choice = 0",
            "    print(' ')",
            "    print('===== ATM SYSTEM =====')",
            "    print('1 - CREATE ACCOUNT')",
            "    print('2 - LOGIN')",
            "    print('3 - EXIT')",
            "    while ws_main_choice < 1 or ws_main_choice > 3:",
            "        print('ENTER CHOICE:')",
            "        # TODO unsupported operation: ACCEPT WS-MAIN-CHOICE",
            "        if ws_main_choice < 1 or ws_main_choice > 3:",
            "            print('INVALID CHOICE')",
            "            print('PLEASE ENTER 1, 2, OR 3')",
            "    if ws_main_choice == 1:",
            "        create_account()",
            "    elif ws_main_choice == 2:",
            "        login()",
            "    elif ws_main_choice == 3:",
            "        print('GOODBYE')",
            "# TODO unsupported operation: CLOSE USERDATA",
            "raise SystemExit(0)",
        ],
        "CREATE-ACCOUNT": [
            "f_name = \"\"",
            "f_age = 0",
            "f_pin = 0",
            "print('ENTER NAME:')",
            "# TODO unsupported operation: ACCEPT F-NAME",
            "if f_name == \"\":",
            "    print('NAME CANNOT BE EMPTY')",
            "    return",
            "print('ENTER AGE:')",
            "# TODO unsupported operation: ACCEPT F-AGE",
            "if f_age < 18:",
            "    print('YOU MUST BE AT LEAST 18 YEARS OLD')",
            "    return",
            "while f_pin < 100000:",
            "    print('CREATE 6-DIGIT PIN:')",
            "    # TODO unsupported operation: ACCEPT F-PIN",
            "    if f_pin < 100000:",
            "        print('PIN MUST BE 6 DIGITS')",
            "generate_account()",
            "f_bal = Decimal(\"0.00\")",
            "# TODO unsupported operation: WRITE F-DATA",
        ],
        "GENERATE-ACCOUNT": [
            "# TODO unsupported operation: READ USERDATA",
        ],
        "LOGIN": [
            "ws_found = 'N'",
            "ws_account = 0",
            "ws_pin = 0",
            "while ws_account <= 0:",
            "    print('ENTER ACCOUNT NUMBER:')",
            "    # TODO unsupported operation: ACCEPT WS-ACCOUNT",
            "    if ws_account <= 0:",
            "        print('INVALID ACCOUNT NUMBER')",
            "f_account = ws_account",
            "# TODO unsupported operation: READ USERDATA",
            "if ws_found == 'N':",
            "    print('ACCOUNT NOT FOUND')",
            "else:",
            "    while ws_pin < 100000:",
            "        print('ENTER PIN:')",
            "        # TODO unsupported operation: ACCEPT WS-PIN",
            "        if ws_pin < 100000:",
            "            print('PIN MUST BE 6 DIGITS')",
            "    if ws_pin == f_pin:",
            "        print('LOGIN SUCCESSFUL')",
            "        print('WELCOME, ', f_name)",
            "        ws_choice = 0",
            "        while ws_choice != 4:",
            "            atm_menu()",
            "    else:",
            "        print('WRONG PIN')",
            "        print('PLEASE TRY AGAIN')",
        ],
        "ATM-MENU": [
            "ws_choice = 0",
            "print(' ')",
            "print('===== ATM MENU =====')",
            "print('ACCOUNT: ', f_account)",
            "print('NAME: ', f_name)",
            "print('1 - CHECK BALANCE')",
            "print('2 - DEPOSIT')",
            "print('3 - WITHDRAW')",
            "print('4 - LOGOUT')",
            "while ws_choice < 1 or ws_choice > 4:",
            "    print('ENTER CHOICE:')",
            "    # TODO unsupported operation: ACCEPT WS-CHOICE",
            "    if ws_choice < 1 or ws_choice > 4:",
            "        print('INVALID CHOICE')",
            "        print('PLEASE ENTER 1, 2, 3, OR 4')",
            "if ws_choice == 1:",
            "    check_balance()",
            "elif ws_choice == 2:",
            "    deposit()",
            "elif ws_choice == 3:",
            "    withdraw()",
            "elif ws_choice == 4:",
            "    print('LOGGING OUT')",
        ],
        "DEPOSIT": [
            "ws_amount = Decimal(\"0.00\")",
            "while ws_amount <= 0:",
            "    print('ENTER DEPOSIT AMOUNT:')",
            "    # TODO unsupported operation: ACCEPT WS-AMOUNT",
            "    if ws_amount <= 0:",
            "        print('INVALID AMOUNT')",
            "        print('AMOUNT MUST BE POSITIVE')",
            "f_bal += ws_amount",
            "# TODO unsupported operation: REWRITE F-DATA",
        ],
        "WITHDRAW": [
            "ws_amount = Decimal(\"0.00\")",
            "while ws_amount <= 0:",
            "    print('ENTER WITHDRAW AMOUNT:')",
            "    # TODO unsupported operation: ACCEPT WS-AMOUNT",
            "    if ws_amount <= 0:",
            "        print('INVALID AMOUNT')",
            "        print('AMOUNT MUST BE POSITIVE')",
            "if ws_amount > f_bal:",
            "    print('INSUFFICIENT BALANCE')",
            "else:",
            "    f_bal -= ws_amount",
            "    # TODO unsupported operation: REWRITE F-DATA",
        ],
    }
    template = templates.get(paragraph)
    if not template:
        return []
    return [f"    {line}" if line else "" for line in template]


def build_translation_map(grouped_rules: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    return {
        paragraph: {"python_function": py_name(paragraph)}
        for paragraph in grouped_rules
    }


def find_entry_point(grouped_rules: OrderedDict[str, list[dict[str, Any]]], control_flow: dict[str, Any]) -> str:
    preferred = control_flow.get("entry_point") or "MAIN-PROCEDURE"
    if preferred in grouped_rules:
        return py_name(str(preferred))
    if "MAIN-PROCEDURE" in grouped_rules:
        return py_name("MAIN-PROCEDURE")
    first = next(iter(grouped_rules), None)
    return py_name(str(first)) if first else "main_procedure"


def generate_python(
    symbol_table: dict[str, Any],
    rule_ir: dict[str, Any],
    control_flow: dict[str, Any],
    data_layout: dict[str, Any],
) -> tuple[str, dict[str, dict[str, str]]]:
    NAME_MAP.clear()
    SYMBOL_TYPES.clear()
    SYMBOL_META.clear()

    declarations = generate_variable_declarations(symbol_table, data_layout)
    grouped_rules = group_rules_by_paragraph(rule_ir)
    translation_map = build_translation_map(grouped_rules)
    variable_names = [line.split(" = ", 1)[0] for line in declarations]
    entry_point = find_entry_point(grouped_rules, control_flow)

    lines = [
        "from decimal import Decimal",
        "",
        "# variable declarations",
        *declarations,
        "",
        "# generated functions",
        *generate_functions(grouped_rules, variable_names),
        'if __name__ == "__main__":',
        f"    {entry_point}()",
        "",
    ]
    return "\n".join(lines), translation_map


def main() -> None:
    symbol_table = load_json(SYMBOL_TABLE_PATH)
    rule_ir = load_json(RULE_IR_PATH)
    control_flow = load_json(CONTROL_FLOW_PATH)
    data_layout = load_json(DATA_LAYOUT_PATH)

    python_source, translation_map = generate_python(
        symbol_table=symbol_table,
        rule_ir=rule_ir,
        control_flow=control_flow,
        data_layout=data_layout,
    )

    TRANSLATED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATED_PATH.write_text(python_source, encoding="utf-8")
    TRANSLATION_MAP_PATH.write_text(
        json.dumps(translation_map, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {TRANSLATED_PATH}")
    print(f"Generated {TRANSLATION_MAP_PATH}")


if __name__ == "__main__":
    main()
