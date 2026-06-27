"""End-to-end COBOL semantic migration pipeline.

One command accepts a COBOL source file, regenerates the semantic JSON outputs,
runs the deterministic translator, and patches unsupported blocks into a final
Python file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT_DIR / "outputs"
TRANSLATED_DIR = ROOT_DIR / "translated"
PARSER_DIR = ROOT_DIR / "src" / "parser"

if str(PARSER_DIR) not in sys.path:
    sys.path.insert(0, str(PARSER_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from control_flow import save_control_flow
from data_layout import build_data_layout
from paragraph_map import save_paragraph_map
from rule_ir import save_rule_ir
from structure import save_program_structure
from summary import build_summary, write_summary
from symbol_table import save_symbol_table

from src.translator import rule_based


PROGRAM_STRUCTURE_PATH = OUTPUTS_DIR / "program_structure.json"
SYMBOL_TABLE_PATH = OUTPUTS_DIR / "symbol_table.json"
PARAGRAPH_MAP_PATH = OUTPUTS_DIR / "paragraph_map.json"
CONTROL_FLOW_PATH = OUTPUTS_DIR / "control_flow.json"
DATA_LAYOUT_PATH = OUTPUTS_DIR / "data_layout.json"
RULE_IR_PATH = OUTPUTS_DIR / "rule_ir.json"
PROGRAM_SUMMARY_PATH = OUTPUTS_DIR / "program_summary.md"
MONEY_NAME_RE = re.compile(r"(BAL|BALANCE|AMOUNT|AMT|PRICE|TOTAL|PAY|SALARY|WAGE|FEE|COST)", re.IGNORECASE)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_semantic_parser(cobol_path: Path) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    print("1/4 Generating semantic parser outputs...", flush=True)
    save_program_structure(str(cobol_path), str(PROGRAM_STRUCTURE_PATH))
    save_symbol_table(str(cobol_path), str(SYMBOL_TABLE_PATH))
    save_paragraph_map(str(cobol_path), str(PARAGRAPH_MAP_PATH))
    save_control_flow(str(cobol_path), str(PARAGRAPH_MAP_PATH), str(CONTROL_FLOW_PATH))
    build_data_layout(str(PROGRAM_STRUCTURE_PATH), str(SYMBOL_TABLE_PATH), str(DATA_LAYOUT_PATH))
    save_rule_ir(str(cobol_path), str(PARAGRAPH_MAP_PATH), str(RULE_IR_PATH))

    summary = build_summary()
    write_summary(str(PROGRAM_SUMMARY_PATH), summary)


def _variable_meanings(symbol_table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    variables: dict[str, dict[str, Any]] = {}
    for name, meta in symbol_table.items():
        if not isinstance(meta, dict):
            continue
        variable_type = meta.get("python_type") or meta.get("type")
        if MONEY_NAME_RE.search(str(name)):
            variable_type = "Decimal"
        variables[name] = {
            "python_name": meta.get("python_name"),
            "kind": meta.get("kind"),
            "type": variable_type,
            "pic": meta.get("pic"),
            "scale": meta.get("scale"),
            "is_money": bool(meta.get("is_money", False) or MONEY_NAME_RE.search(str(name))),
        }
    return variables


def _paragraph_meanings(
    paragraph_map: dict[str, Any],
    control_flow: dict[str, Any],
    rule_ir: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    rules_by_paragraph: dict[str, list[dict[str, Any]]] = {}
    for rule in rule_ir.get("rules") or []:
        paragraph = rule.get("paragraph")
        if paragraph:
            rules_by_paragraph.setdefault(str(paragraph), []).append(rule)

    outgoing_edges: dict[str, list[str]] = {}
    for edge in control_flow.get("edges") or []:
        source = edge.get("from") or edge.get("source")
        target = edge.get("to") or edge.get("target")
        if source and target:
            outgoing_edges.setdefault(str(source), []).append(str(target))

    meanings: dict[str, dict[str, Any]] = {}
    for paragraph, meta in paragraph_map.items():
        rules = rules_by_paragraph.get(paragraph, [])
        meanings[paragraph] = {
            "purpose": meta.get("purpose") if isinstance(meta, dict) else None,
            "called_paragraphs": outgoing_edges.get(paragraph, []),
            "rule_count": len(rules),
            "operations": [
                str(rule.get("type") or rule.get("operation"))
                for rule in rules
                if rule.get("type") or rule.get("operation")
            ],
        }
    return meanings


def build_semantic_meaning(cobol_path: Path, output_path: Path) -> None:
    print("2/4 Writing semantic meaning...", flush=True)
    structure = read_json(PROGRAM_STRUCTURE_PATH)
    symbol_table = read_json(SYMBOL_TABLE_PATH)
    paragraph_map = read_json(PARAGRAPH_MAP_PATH)
    control_flow = read_json(CONTROL_FLOW_PATH)
    data_layout = read_json(DATA_LAYOUT_PATH)
    rule_ir = read_json(RULE_IR_PATH)

    semantic_meaning = {
        "source_file": str(cobol_path),
        "program_name": structure.get("program_name"),
        "entry_point": structure.get("entry_point"),
        "overview": {
            "language": structure.get("language"),
            "dialect": structure.get("dialect"),
            "program_type": structure.get("program_type"),
            "paragraph_count": len(structure.get("paragraphs") or []),
            "rule_count": len(rule_ir.get("rules") or []),
        },
        "paragraphs": _paragraph_meanings(paragraph_map, control_flow, rule_ir),
        "variables": _variable_meanings(symbol_table),
        "files": data_layout.get("files", {}),
        "control_flow": {
            "entry_point": control_flow.get("entry_point"),
            "nodes": control_flow.get("nodes", []),
            "edges": control_flow.get("edges", []),
            "loops": control_flow.get("loops", []),
        },
    }
    write_json(output_path, semantic_meaning)


def default_output_paths(cobol_path: Path) -> dict[str, Path]:
    stem = cobol_path.stem.lower()
    output_dir = OUTPUTS_DIR / stem
    translated_dir = TRANSLATED_DIR / stem
    return {
        "output_dir": output_dir,
        "translated_dir": translated_dir,
        "program_structure": output_dir / "program_structure.json",
        "symbol_table": output_dir / "symbol_table.json",
        "paragraph_map": output_dir / "paragraph_map.json",
        "control_flow": output_dir / "control_flow.json",
        "data_layout": output_dir / "data_layout.json",
        "rule_ir": output_dir / "rule_ir.json",
        "program_summary": output_dir / "program_summary.md",
        "semantic": output_dir / "semantic_meaning.json",
        "translated": translated_dir / "translated.py",
        "final": translated_dir / "translated_final.py",
        "translation_map": output_dir / "translation_map.json",
    }


def write_named_parser_outputs(paths: dict[str, Path]) -> None:
    copies = {
        PROGRAM_STRUCTURE_PATH: paths["program_structure"],
        SYMBOL_TABLE_PATH: paths["symbol_table"],
        PARAGRAPH_MAP_PATH: paths["paragraph_map"],
        CONTROL_FLOW_PATH: paths["control_flow"],
        DATA_LAYOUT_PATH: paths["data_layout"],
        RULE_IR_PATH: paths["rule_ir"],
        PROGRAM_SUMMARY_PATH: paths["program_summary"],
    }
    for source, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def cleanup_top_level_generated_files() -> None:
    """Remove compatibility artifacts after per-program outputs are written."""
    for directory in (OUTPUTS_DIR, TRANSLATED_DIR):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file():
                path.unlink()


def run_rule_based_translation(translated_output: Path, translation_map_output: Path) -> None:
    print("3/4 Generating rule-based Python...", flush=True)
    symbol_table = read_json(SYMBOL_TABLE_PATH)
    rule_ir = read_json(RULE_IR_PATH)
    control_flow = read_json(CONTROL_FLOW_PATH)
    data_layout = read_json(DATA_LAYOUT_PATH)

    python_source, translation_map = rule_based.generate_python(
        symbol_table=symbol_table,
        rule_ir=rule_ir,
        control_flow=control_flow,
        data_layout=data_layout,
    )

    translated_output.parent.mkdir(parents=True, exist_ok=True)
    translation_map_output.parent.mkdir(parents=True, exist_ok=True)
    translated_output.write_text(python_source, encoding="utf-8")
    translation_map_output.write_text(
        json.dumps(translation_map, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {translated_output}", flush=True)
    print(f"Generated {translation_map_output}", flush=True)


def run_fallback(translated_output: Path, final_output: Path, use_llm: bool) -> None:
    print("4/4 Generating final Python...", flush=True)
    command = [
        sys.executable,
        "-m",
        "src.translator.llm_fallback",
        str(translated_output.relative_to(ROOT_DIR) if translated_output.is_relative_to(ROOT_DIR) else translated_output),
        "-o",
        str(final_output.relative_to(ROOT_DIR) if final_output.is_relative_to(ROOT_DIR) else final_output),
    ]
    if not use_llm:
        command.append("--no-llm")
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate semantic meaning and final Python from one COBOL file.",
    )
    parser.add_argument(
        "cobol_file",
        help="COBOL source file to process, for example data/cobol/ATM.cob",
    )
    parser.add_argument(
        "--semantic-output",
        default=None,
        help="Semantic meaning JSON output path. Default: outputs/<input>/semantic_meaning.json",
    )
    parser.add_argument(
        "--translated-output",
        default=None,
        help="Rule-based Python output path. Default: translated/<input>/translated.py",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Final Python output path. Default: translated/<input>/translated_final.py",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Call the LLM fallback for unsupported blocks. Default uses deterministic fallback.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(ROOT_DIR)

    cobol_path = Path(args.cobol_file)
    if not cobol_path.is_absolute():
        cobol_path = ROOT_DIR / cobol_path
    if not cobol_path.exists():
        raise FileNotFoundError(f"COBOL source file not found: {cobol_path}")

    default_paths = default_output_paths(cobol_path)

    semantic_output = Path(args.semantic_output or default_paths["semantic"])
    if not semantic_output.is_absolute():
        semantic_output = ROOT_DIR / semantic_output
    translated_output = Path(args.translated_output or default_paths["translated"])
    if not translated_output.is_absolute():
        translated_output = ROOT_DIR / translated_output
    final_output = Path(args.output or default_paths["final"])
    if not final_output.is_absolute():
        final_output = ROOT_DIR / final_output
    translation_map_output = default_paths["translation_map"]

    print(f"Source COBOL: {cobol_path}", flush=True)
    run_semantic_parser(cobol_path)
    build_semantic_meaning(cobol_path, semantic_output)
    write_named_parser_outputs(default_paths)
    run_rule_based_translation(translated_output, translation_map_output)
    run_fallback(translated_output, final_output, use_llm=args.use_llm)
    cleanup_top_level_generated_files()

    print("Pipeline complete.", flush=True)
    print(f"Output folder: {default_paths['output_dir']}", flush=True)
    print(f"Translated folder: {default_paths['translated_dir']}", flush=True)
    print(f"Program structure: {default_paths['program_structure']}", flush=True)
    print(f"Symbol table: {default_paths['symbol_table']}", flush=True)
    print(f"Rule IR: {default_paths['rule_ir']}", flush=True)
    print(f"Semantic meaning: {semantic_output}", flush=True)
    print(f"Rule-based Python: {translated_output}", flush=True)
    print(f"Final Python: {final_output}", flush=True)


if __name__ == "__main__":
    main()
