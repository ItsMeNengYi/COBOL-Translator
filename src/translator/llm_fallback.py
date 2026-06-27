"""LLM fallback helpers for unsupported translated COBOL rules.

The rule-based translator remains the source of truth. This module only
identifies TODO placeholders and asks an LLM to translate those specific rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.translator.prompt_builder import build_translation_context, build_translation_prompt
from src.translator.rule_based import (
    CONTROL_FLOW_PATH,
    DATA_LAYOUT_PATH,
    RULE_IR_PATH,
    SYMBOL_TABLE_PATH,
    load_json,
    py_name,
)


SUPPORTED_RULE_TYPES = {
    "MOVE",
    "ADD",
    "SUBTRACT",
    "COMPUTE",
    "DISPLAY",
    "PERFORM",
    "IF",
    "EVALUATE",
    "PERFORM_UNTIL",
    "EXIT_PARAGRAPH",
    "EXIT",
    "CONTINUE",
    "STOP_RUN",
}

MONEY_NAME_RE = re.compile(r"(BAL|BALANCE|AMOUNT|AMT|PRICE|TOTAL|PAY|SALARY|WAGE|FEE|COST)", re.IGNORECASE)

TODO_RE = re.compile(
    r"^(?P<indent>\s*)# TODO unsupported operation: "
    r"(?P<operation>[A-Z_ -]+?)(?:\s+(?P<detail>[A-Z0-9-]+))?\s*$"
)


def _strip_markdown_fence(code: str) -> str:
    text = code.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip("\n")


def _indent_generated_code(code: str, indent: str) -> str:
    cleaned = _strip_markdown_fence(code)
    if not cleaned:
        return f"{indent}pass"

    lines = cleaned.splitlines()
    nonempty_lines = [line for line in lines if line.strip()]
    min_indent = min(
        len(line) - len(line.lstrip())
        for line in nonempty_lines
    ) if nonempty_lines else 0

    normalized = [
        line[min_indent:] if line.strip() else ""
        for line in lines
    ]
    return "\n".join(
        f"{indent}{line}" if line else ""
        for line in normalized
    )


def _sanitize_generated_python(code: str) -> str:
    cleaned = _strip_markdown_fence(code)
    rejected_prefixes = (
        "import ",
        "from ",
        "def ",
        "class ",
        "global ",
        "nonlocal ",
    )
    safe_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            safe_lines.append(line)
            continue
        if stripped.startswith(rejected_prefixes):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:\s*[^=]+=", stripped):
            name, value = stripped.split("=", 1)
            safe_lines.append(f"{name.split(':', 1)[0].strip()} = {value.strip()}")
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:\s*[^=]+$", stripped):
            continue
        safe_lines.append(line)

    sanitized = "\n".join(safe_lines).strip()
    return sanitized or "pass"


def _source_compiles(source: str) -> bool:
    try:
        compile(source, "translated/atm_translated_final.py", "exec")
    except SyntaxError:
        return False
    return True


def _remove_redundant_plain_passes(source: str) -> str:
    cleaned = "\n".join(
        line for line in source.splitlines()
        if line.strip() != "pass"
    )
    if source.endswith("\n"):
        cleaned += "\n"
    return cleaned if _source_compiles(cleaned) else source


def _preview_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": block.get("rule_id"),
            "paragraph": block.get("paragraph"),
            "unsupported_type": block.get("unsupported_type"),
            "line_number": block.get("line_number"),
            "todo_text": block.get("todo_text"),
        }
        for block in blocks
    ]


def _data_layout_file(data_layout: dict[str, Any], file_name: str | None = None) -> dict[str, Any]:
    files = data_layout.get("files") or {}
    if file_name and file_name in files:
        return files[file_name]
    return next(iter(files.values()), {})


def _assigned_file_path(data_layout: dict[str, Any], file_name: str | None = None) -> str:
    file_info = _data_layout_file(data_layout, file_name)
    return str(file_info.get("assign_to") or "atm_accounts.dat")


def _record_fields(data_layout: dict[str, Any], file_name: str | None = None) -> list[dict[str, Any]]:
    return list(_data_layout_file(data_layout, file_name).get("fields") or [])


def _symbol_type(cobol_name: str, symbol_table: dict[str, Any], data_layout: dict[str, Any]) -> str:
    if MONEY_NAME_RE.search(str(cobol_name)):
        return "Decimal"
    for field in _record_fields(data_layout):
        if field.get("name") == cobol_name:
            field_type = "Decimal" if MONEY_NAME_RE.search(str(field.get("name"))) else field.get("type")
            return str(field_type or "str")
    symbol = symbol_table.get(cobol_name, {})
    if isinstance(symbol, dict):
        if symbol.get("scale"):
            return "Decimal"
        return str(symbol.get("python_type") or symbol.get("type") or "str")
    return "str"


def _assignment_from_ir_action(action: dict[str, Any]) -> str | None:
    operation = str(action.get("operation") or action.get("type") or "").upper()
    if operation != "MOVE":
        return None
    target = py_name(str(action.get("target", "")))
    source = action.get("source", "")
    if isinstance(source, str) and not source.lstrip("-").isdigit():
        value = repr(source)
    else:
        value = str(source)
    return f"{target} = {value}"


def _display_from_ir_action(action: dict[str, Any]) -> str | None:
    operation = str(action.get("operation") or action.get("type") or "").upper()
    if operation != "DISPLAY":
        return None
    if "parts" in action:
        parts = [
            py_name(str(part)) if re.fullmatch(r"[A-Z][A-Z0-9-]*", str(part)) else repr(part)
            for part in action.get("parts") or []
        ]
        return f"print({', '.join(parts)})" if parts else "print(\"\")"
    if "source" in action:
        return f"print({py_name(str(action['source']))})"
    return f"print({action.get('value', '')!r})"


def _branch_fallback_lines(rule: dict[str, Any], branch_name: str) -> list[str]:
    lines: list[str] = []
    for action in rule.get(branch_name) or []:
        assignment = _assignment_from_ir_action(action)
        if assignment:
            lines.append(assignment)
            continue
        display = _display_from_ir_action(action)
        if display:
            lines.append(display)
    return lines


def _deterministic_fallback(
    block: dict[str, Any],
    symbol_table: dict[str, Any],
    data_layout: dict[str, Any],
) -> str:
    action = block.get("unsupported_action") or {}
    rule = block.get("rule") or action
    operation = str(action.get("operation") or action.get("type") or block.get("unsupported_type") or "").upper()

    if operation == "ACCEPT":
        target_name = str(action.get("target", ""))
        target = py_name(target_name)
        target_type = _symbol_type(target_name, symbol_table, data_layout)
        if target_type == "Decimal":
            return "\n".join([
                "_raw_input = input()",
                "try:",
                f"    {target} = Decimal(_raw_input)",
                "except Exception:",
                f"    {target} = Decimal(\"0.00\")",
            ])
        if target_type == "int":
            return "\n".join([
                "_raw_input = input()",
                "try:",
                f"    {target} = int(_raw_input)",
                "except Exception:",
                f"    {target} = 0",
            ])
        return f"{target} = input()"

    if operation == "OPEN":
        file_name = action.get("file")
        file_path = _assigned_file_path(data_layout, file_name)
        mode = str(action.get("mode") or "I-O").upper()
        python_mode = "w+" if mode == "OUTPUT" else "a+"
        return "\n".join([
            "try:",
            f"    globals()[\"userdata_file\"] = open({file_path!r}, {python_mode!r})",
            "    ws_file_status = \"00\"",
            "except OSError:",
            "    ws_file_status = \"35\"",
        ])

    if operation == "CLOSE":
        return "\n".join([
            "_userdata_file = globals().get(\"userdata_file\")",
            "if _userdata_file:",
            "    _userdata_file.close()",
            "ws_file_status = \"00\"",
        ])

    if operation in {"WRITE", "REWRITE"}:
        file_name = action.get("file")
        fields = _record_fields(data_layout, file_name)
        record_values = ", ".join(
            f"{field['python_name']!r}: {field['python_name']}"
            for field in fields
            if field.get("python_name")
        )
        lines = [
            "_userdata_records = globals().setdefault(\"userdata_records\", {})",
            f"_userdata_records[f_account] = {{{record_values}}}",
            "ws_file_status = \"00\"",
        ]
        lines.extend(_branch_fallback_lines(rule, "not_invalid_key"))
        return "\n".join(lines)

    if operation == "READ":
        if block.get("paragraph") == "GENERATE-ACCOUNT":
            return "\n".join([
                "_userdata_records = globals().setdefault(\"userdata_records\", {})",
                "_random = __import__(\"random\")",
                "while True:",
                "    f_account = _random.randint(1000000000, 9999999999)",
                "    if f_account not in _userdata_records:",
                "        ws_file_status = \"23\"",
                "        break",
            ])

        file_name = action.get("file")
        fields = _record_fields(data_layout, file_name)
        lines = [
            "_userdata_records = globals().setdefault(\"userdata_records\", {})",
            "_record = _userdata_records.get(f_account)",
            "if _record is None:",
            "    ws_file_status = \"23\"",
        ]
        invalid_lines = _branch_fallback_lines(rule, "invalid_key")
        lines.extend(f"    {line}" for line in (invalid_lines or ["pass"]))
        lines.extend([
            "else:",
            "    ws_file_status = \"00\"",
        ])
        for field in fields:
            python_name = field.get("python_name")
            if python_name:
                lines.append(f"    {python_name} = _record.get({python_name!r}, {python_name})")
        not_invalid_lines = _branch_fallback_lines(rule, "not_invalid_key")
        lines.extend(f"    {line}" for line in not_invalid_lines)
        return "\n".join(lines)

    return f"pass  # unsupported deterministic fallback for {block['rule_id']} {block['unsupported_type']}"


def _safe_fallback_code(
    code: str,
    blocks: list[dict[str, Any]],
    symbol_table: dict[str, Any],
    data_layout: dict[str, Any],
) -> str:
    patched_code = code
    for block in blocks:
        replacement = _indent_generated_code(
            _deterministic_fallback(block, symbol_table, data_layout),
            block["indent"],
        )
        patched_code = patched_code.replace(block["todo_line"], replacement, 1)
    return patched_code


def load_openai_api_key() -> str | None:
    """Load OPENAI_API_KEY from the environment or local .env file."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=env_path)
    return os.getenv("OPENAI_API_KEY")


def _normalize_unsupported_type(operation: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", operation.upper()).strip("_")


def _action_detail(action: dict[str, Any]) -> str | None:
    for key in ("target", "file", "record"):
        value = action.get(key)
        if value:
            return str(value)
    return None


def _iter_unsupported_from_rule(rule: dict[str, Any]) -> list[dict[str, Any]]:
    rule_id = rule.get("rule_id")
    paragraph = rule.get("paragraph")
    found: list[dict[str, Any]] = []

    def visit(action: dict[str, Any], parent_rule: dict[str, Any]) -> None:
        operation = str(action.get("operation") or action.get("type") or "").upper()
        if operation == "IF":
            for branch_name in ("true_branch", "false_branch"):
                for child in action.get(branch_name) or []:
                    visit(child, parent_rule)
            return
        if operation == "EVALUATE":
            for case in action.get("cases") or []:
                for child in case.get("actions") or []:
                    visit(child, parent_rule)
            return
        if operation and operation not in SUPPORTED_RULE_TYPES:
            found.append(
                {
                    "rule_id": parent_rule.get("rule_id"),
                    "paragraph": parent_rule.get("paragraph"),
                    "unsupported_type": _normalize_unsupported_type(operation),
                    "detail": _action_detail(action),
                    "unsupported_action": action,
                    "rule": parent_rule,
                }
            )

    rule_type = str(rule.get("type") or rule.get("operation") or "").upper()
    if rule_type in {"IF", "EVALUATE"}:
        visit(rule, rule)
    elif rule_type and rule_type not in SUPPORTED_RULE_TYPES:
        found.append(
            {
                "rule_id": rule_id,
                "paragraph": paragraph,
                "unsupported_type": _normalize_unsupported_type(rule_type),
                "detail": _action_detail(rule),
                "unsupported_action": rule,
                "rule": rule,
            }
        )
    return found


def _unsupported_rules_by_paragraph(rule_ir: dict[str, Any]) -> dict[str, deque[dict[str, Any]]]:
    by_paragraph: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for rule in rule_ir.get("rules") or []:
        for unsupported in _iter_unsupported_from_rule(rule):
            by_paragraph[str(unsupported.get("paragraph"))].append(unsupported)
    return by_paragraph


def _paragraph_by_function(rule_ir: dict[str, Any]) -> dict[str, str]:
    paragraphs = {
        str(rule.get("paragraph"))
        for rule in rule_ir.get("rules") or []
        if rule.get("paragraph")
    }
    return {py_name(paragraph): paragraph for paragraph in paragraphs}


def find_unsupported_blocks(
    translated_python_path: str | Path,
    rule_ir: dict[str, Any],
) -> list[dict[str, Any]]:
    """Find TODO placeholders and correlate them to rule_ir entries."""
    path = Path(translated_python_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    rules_by_paragraph = _unsupported_rules_by_paragraph(rule_ir)
    paragraph_by_function = _paragraph_by_function(rule_ir)

    current_paragraph: str | None = None
    blocks: list[dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("def ") and line.rstrip().endswith(":"):
            function_name = line.split("def ", 1)[1].split("(", 1)[0]
            current_paragraph = paragraph_by_function.get(function_name)
            continue

        match = TODO_RE.match(line)
        if not match:
            continue

        unsupported_type = _normalize_unsupported_type(match.group("operation"))
        todo_detail = match.group("detail")
        rule_match = None
        if current_paragraph is not None:
            candidates = rules_by_paragraph[current_paragraph]
            for index, candidate in enumerate(candidates):
                detail_matches = not todo_detail or candidate.get("detail") == todo_detail
                if candidate["unsupported_type"] == unsupported_type and detail_matches:
                    rule_match = candidate
                    del candidates[index]
                    break

        block = {
            "rule_id": rule_match.get("rule_id") if rule_match else None,
            "paragraph": current_paragraph,
            "unsupported_type": unsupported_type,
            "detail": todo_detail,
            "todo_text": match.group(0).strip(),
            "todo_line": line,
            "line_number": line_number,
            "indent": match.group("indent"),
        }
        if rule_match:
            block["rule"] = rule_match["rule"]
            block["unsupported_action"] = rule_match["unsupported_action"]
        blocks.append(block)

    return blocks


def translate_with_llm(context: dict[str, Any]) -> dict[str, Any]:
    """Translate one unsupported rule using OpenAI as a fallback only."""
    from openai import OpenAI

    api_key = load_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for LLM fallback translation")

    client = OpenAI(api_key=api_key)
    prompt = build_translation_prompt(context)
    response = client.responses.create(
        model="gpt-5.5-thinking",
        input=prompt,
        timeout=30,
    )
    generated_python = response.output_text.strip()

    return {
        "rule_id": context.get("rule", {}).get("rule_id"),
        "generated_python": generated_python,
        "confidence": 0.0 if not generated_python else 1.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch unsupported TODO blocks in translated Python.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="translated/atm_translated.py",
        help="Translated Python file to patch. Default: translated/atm_translated.py",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="translated/atm_translated_final.py",
        help="Output Python file to write. Default: translated/atm_translated_final.py",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use deterministic fallback only; do not call the LLM.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Running LLM fallback...", flush=True)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}", flush=True)
        return

    print("Loading files...", flush=True)
    symbol_table = load_json(SYMBOL_TABLE_PATH)
    rule_ir = load_json(RULE_IR_PATH)
    control_flow = load_json(CONTROL_FLOW_PATH)
    data_layout = load_json(DATA_LAYOUT_PATH)

    print(f"Checking {input_path}...", flush=True)
    code = input_path.read_text(encoding="utf-8")

    if "# TODO unsupported" not in code:
        print("No unsupported TODO blocks found.", flush=True)
        print("Copying rule-based file to final output.", flush=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        print(f"Created: {output_path}", flush=True)
        return

    print("Finding unsupported TODO blocks...", flush=True)
    unsupported_blocks = find_unsupported_blocks(input_path, rule_ir)

    print(f"Found {len(unsupported_blocks)} unsupported blocks", flush=True)
    print(json.dumps(_preview_blocks(unsupported_blocks), indent=2, default=str), flush=True)

    patched_code = code
    llm_enabled = not args.no_llm
    for block in unsupported_blocks:
        if "rule" not in block:
            print(f"Skipping block without matched rule: {block}", flush=True)
            continue

        print(
            "Translating "
            f"{block['rule_id']} "
            f"{block['paragraph']} "
            f"{block['unsupported_type']} "
            f"line {block['line_number']}...",
            flush=True,
        )
        context = build_translation_context(
            block["rule"],
            symbol_table,
            control_flow,
            data_layout,
        )
        context["unsupported_block"] = {
            "rule_id": block.get("rule_id"),
            "paragraph": block.get("paragraph"),
            "unsupported_type": block.get("unsupported_type"),
            "todo_text": block.get("todo_text"),
            "unsupported_action": block.get("unsupported_action"),
        }
        if llm_enabled:
            try:
                llm_result = translate_with_llm(context)
            except Exception as exc:
                print(
                    f"LLM failed for {block['rule_id']} {block['unsupported_type']}: {exc}",
                    flush=True,
                )
                print("Disabling LLM calls for remaining unsupported blocks.", flush=True)
                llm_enabled = False
                llm_result = {
                    "generated_python": _deterministic_fallback(block, symbol_table, data_layout)
                }
        else:
            llm_result = {
                "generated_python": _deterministic_fallback(block, symbol_table, data_layout)
            }
        generated_python = _sanitize_generated_python(
            llm_result.get("generated_python", "")
        )
        if not generated_python.strip():
            print(f"Skipping empty LLM output for {block['rule_id']}", flush=True)
            continue

        todo_text = block["todo_line"]
        replacement = _indent_generated_code(generated_python, block["indent"])
        candidate_code = patched_code.replace(
            todo_text,
            replacement,
            1,
        )
        if _source_compiles(candidate_code):
            patched_code = candidate_code
        else:
            print(
                "Rejected generated output that broke Python syntax for "
                f"{block['rule_id']} {block['unsupported_type']}",
                flush=True,
            )
            safe_replacement = _indent_generated_code(
                _deterministic_fallback(block, symbol_table, data_layout),
                block["indent"],
            )
            patched_code = patched_code.replace(todo_text, safe_replacement, 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    patched_code = _remove_redundant_plain_passes(patched_code)
    print("Remaining TODO count:", patched_code.count("# TODO unsupported"), flush=True)
    if not _source_compiles(patched_code):
        print("Final patched code does not compile. Overwriting with safe fallback output.", flush=True)
        patched_code = _safe_fallback_code(code, unsupported_blocks, symbol_table, data_layout)
        print("Remaining TODO count:", patched_code.count("# TODO unsupported"), flush=True)
    print(f"Overwriting: {output_path}", flush=True)
    output_path.write_text(patched_code, encoding="utf-8")

    print(f"Created: {output_path}", flush=True)


if __name__ == "__main__":
    main()
