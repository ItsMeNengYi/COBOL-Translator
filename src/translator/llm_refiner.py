"""Patch unsupported TODOs with auditable LLM fallback translations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.translator.llm_fallback import find_unsupported_blocks, load_openai_api_key, translate_with_llm
from src.translator.prompt_builder import build_translation_context
from src.translator.rule_based import (
    CONTROL_FLOW_PATH,
    DATA_LAYOUT_PATH,
    OUTPUTS_DIR,
    RULE_IR_PATH,
    SYMBOL_TABLE_PATH,
    TRANSLATED_PATH,
    load_json,
)


CONFIDENCE_PATH = OUTPUTS_DIR / "translation_confidence.json"
AUDIT_PATH = OUTPUTS_DIR / "translation_audit.json"
TODO_RE = re.compile(r"^(?P<indent>\s*)# TODO unsupported operation: (?P<operation>.+?)\s*$")


def _read_source(translated_python: str | Path) -> tuple[str, Path | None]:
    maybe_path = Path(translated_python)
    if isinstance(translated_python, Path) or maybe_path.exists():
        return maybe_path.read_text(encoding="utf-8"), maybe_path
    return str(translated_python), None


def _indent_code(code: str, indent: str) -> list[str]:
    stripped_lines = code.strip("\n").splitlines()
    if not stripped_lines:
        return [f"{indent}pass"]

    nonempty = [line for line in stripped_lines if line.strip()]
    min_indent = min((len(line) - len(line.lstrip())) for line in nonempty) if nonempty else 0
    normalized = [line[min_indent:] if line.strip() else "" for line in stripped_lines]
    return [f"{indent}{line}" if line else "" for line in normalized]


def _llm_output_by_line(llm_outputs: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(output["line_number"]): output
        for output in llm_outputs
        if output.get("line_number") is not None and output.get("generated_python")
    }


def patch_generated_code(
    translated_python: str | Path,
    llm_outputs: list[dict[str, Any]],
) -> str:
    """Replace only unsupported TODO placeholder lines with LLM output."""
    source, source_path = _read_source(translated_python)
    by_line = _llm_output_by_line(llm_outputs)
    patched_lines: list[str] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        match = TODO_RE.match(line)
        replacement = by_line.get(line_number)
        if match and replacement:
            patched_lines.extend(_indent_code(replacement["generated_python"], match.group("indent")))
        else:
            patched_lines.append(line)

    patched_source = "\n".join(patched_lines) + ("\n" if source.endswith("\n") else "")
    if source_path:
        source_path.write_text(patched_source, encoding="utf-8")
    return patched_source


def compute_translation_confidence(source: str, llm_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    successful_outputs = [
        output for output in llm_outputs
        if output.get("generated_python")
    ]
    successful_llm_lines = sum(
        len([line for line in output["generated_python"].splitlines() if line.strip()])
        for output in successful_outputs
    )
    unsupported = sum(1 for line in source.splitlines() if TODO_RE.match(line))
    rule_based_lines = len(
        [
            line for line in source.splitlines()
            if line.strip() and not TODO_RE.match(line)
        ]
    )
    total_lines = rule_based_lines + successful_llm_lines + unsupported
    confidence = (
        (rule_based_lines + successful_llm_lines) / total_lines
        if total_lines
        else 1.0
    )
    return {
        "rule_based": rule_based_lines,
        "llm_generated": successful_llm_lines,
        "unsupported": unsupported,
        "confidence": round(confidence, 4),
    }


def build_translation_audit(
    rule_ir: dict[str, Any],
    unsupported_blocks: list[dict[str, Any]],
    llm_outputs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    audit = {
        rule["rule_id"]: {"method": "rule_based"}
        for rule in rule_ir.get("rules") or []
        if rule.get("rule_id")
    }
    unsupported_rule_ids = {
        block.get("rule_id")
        for block in unsupported_blocks
        if block.get("rule_id")
    }
    llm_rule_ids = {
        output.get("rule_id")
        for output in llm_outputs
        if output.get("rule_id") and output.get("generated_python")
    }

    for rule_id in unsupported_rule_ids:
        audit[str(rule_id)] = {"method": "unsupported"}
    for rule_id in llm_rule_ids:
        audit[str(rule_id)] = {"method": "llm"}
    return audit


def save_translation_reports(
    source: str,
    rule_ir: dict[str, Any],
    unsupported_blocks: list[dict[str, Any]],
    llm_outputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    confidence = compute_translation_confidence(source, llm_outputs)
    audit = build_translation_audit(rule_ir, unsupported_blocks, llm_outputs)

    CONFIDENCE_PATH.write_text(json.dumps(confidence, indent=2) + "\n", encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    return confidence, audit


def refine_translation(
    translated_python_path: str | Path = TRANSLATED_PATH,
    call_llm: bool = True,
) -> list[dict[str, Any]]:
    """Find unsupported TODOs, translate them, patch only those lines, and audit."""
    symbol_table = load_json(SYMBOL_TABLE_PATH)
    rule_ir = load_json(RULE_IR_PATH)
    control_flow = load_json(CONTROL_FLOW_PATH)
    data_layout = load_json(DATA_LAYOUT_PATH)

    unsupported_blocks = find_unsupported_blocks(translated_python_path, rule_ir)
    llm_outputs: list[dict[str, Any]] = []

    if call_llm:
        for block in unsupported_blocks:
            rule = block.get("rule")
            if not isinstance(rule, dict):
                continue
            context = build_translation_context(rule, symbol_table, control_flow, data_layout)
            output = translate_with_llm(context)
            output.update(
                {
                    "line_number": block.get("line_number"),
                    "paragraph": block.get("paragraph"),
                    "unsupported_type": block.get("unsupported_type"),
                }
            )
            llm_outputs.append(output)
        patched_source = patch_generated_code(translated_python_path, llm_outputs)
    else:
        patched_source = Path(translated_python_path).read_text(encoding="utf-8")

    save_translation_reports(patched_source, rule_ir, unsupported_blocks, llm_outputs)
    return llm_outputs


def _repair_prompt(
    failed_test: dict[str, Any],
    cobol_output: Any,
    python_output: Any,
    rule_ir: dict[str, Any],
) -> str:
    return f"""You are repairing a narrowly scoped COBOL-to-Python migration.

Use only the failing rule and observed outputs below.
Do not rewrite the whole program.
Return JSON only with keys patched_code and reason.

Failed test:
{json.dumps(failed_test, indent=2, sort_keys=True, default=str)}

Original rule:
{json.dumps(rule_ir, indent=2, sort_keys=True, default=str)}

Expected COBOL output:
{json.dumps(cobol_output, indent=2, sort_keys=True, default=str)}

Actual Python output:
{json.dumps(python_output, indent=2, sort_keys=True, default=str)}
"""


def repair_translation(
    failed_test: dict[str, Any],
    cobol_output: Any,
    python_output: Any,
    rule_ir: dict[str, Any],
) -> dict[str, Any]:
    """Ask the LLM to repair one failed translated rule after validation."""
    from openai import OpenAI

    api_key = load_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for LLM repair")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5.5-thinking",
        input=_repair_prompt(failed_test, cobol_output, python_output, rule_ir),
        temperature=0,
    )
    raw_output = response.output_text.strip()

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "patched_code": raw_output,
            "reason": "LLM returned non-JSON repair output",
        }

    return {
        "patched_code": parsed.get("patched_code", ""),
        "reason": parsed.get("reason", ""),
    }


def main() -> None:
    refine_translation(call_llm=True)
    print(f"Generated {CONFIDENCE_PATH}")
    print(f"Generated {AUDIT_PATH}")


if __name__ == "__main__":
    main()
