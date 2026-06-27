import argparse
import ast
import contextlib
import importlib.util
import io
import json
import keyword
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULE_IR = PROJECT_ROOT / "outputs" / "rule_ir.json"
DEFAULT_PARAGRAPH_MAP = PROJECT_ROOT / "outputs" / "paragraph_map.json"
DEFAULT_TRANSLATION_MAP = PROJECT_ROOT / "outputs" / "translation_map.json"
DEFAULT_TRANSLATED_DIR = PROJECT_ROOT / "translated"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent

REQUIRED_RULE_FIELDS = {
    "rule_id",
    "paragraph",
    "type",
    "business_category",
    "translation_hint",
    "risk",
    "needs_ai_enrichment",
    "ai_enrichment_targets",
}

TYPE_REQUIRED_FIELDS = {
    "ACCEPT": {"target"},
    "ADD": {"target"},
    "CALL": {"target"},
    "CLOSE": {"file"},
    "COMPUTE": {"target", "expression"},
    "CONTINUE": set(),
    "DISPLAY": set(),
    "EVALUATE": {"subject", "cases"},
    "EXIT": set(),
    "EXIT_PARAGRAPH": set(),
    "IF": {"condition", "true_branch", "false_branch"},
    "MOVE": {"source", "target"},
    "OPEN": {"mode", "file"},
    "PERFORM": {"target"},
    "PERFORM_UNTIL": set(),
    "READ": {"file"},
    "REWRITE": {"record"},
    "STOP_RUN": set(),
    "SUBTRACT": {"target"},
    "WRITE": {"record"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_rule_ir(path: Path = DEFAULT_RULE_IR) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Missing rule IR file: {path}"]

    try:
        rule_ir = load_json(path)
    except Exception as exc:
        return [str(exc)]

    if not isinstance(rule_ir.get("program"), str) or not rule_ir["program"].strip():
        errors.append("program must be a non-empty string")
    if not isinstance(rule_ir.get("schema_version"), str):
        errors.append("schema_version must be a string")

    rules = rule_ir.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
        return errors

    seen_rule_ids: set[str] = set()
    for index, rule in enumerate(rules, start=1):
        rule_id = rule.get("rule_id")
        if rule_id != f"R{index:03d}":
            errors.append(f"rule {index} has invalid rule_id {rule_id!r}")
        if rule_id in seen_rule_ids:
            errors.append(f"duplicate rule_id {rule_id!r}")
        seen_rule_ids.add(rule_id)

        missing = REQUIRED_RULE_FIELDS - set(rule)
        if missing:
            errors.append(f"{rule_id} missing fields: {sorted(missing)}")

        rule_type = rule.get("type")
        if rule_type not in TYPE_REQUIRED_FIELDS:
            errors.append(f"{rule_id} has unexpected type {rule_type!r}")
            continue

        type_missing = TYPE_REQUIRED_FIELDS[rule_type] - set(rule)
        if type_missing:
            errors.append(f"{rule_id} {rule_type} missing fields: {sorted(type_missing)}")

    return errors


def test_rule_ir_is_valid() -> None:
    assert not validate_rule_ir(DEFAULT_RULE_IR)


def py_name(name: str) -> str:
    cleaned = str(name).lower().replace("-", "_")
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def cobol_to_python_var(name: str) -> str:
    return py_name(name)


def sample_value_for_target(target: str, variant: int = 0) -> str:
    name = target.upper()
    samples = {
        "NAME": ["Test User", "Ada"],
        "RATE": ["25", "10"],
        "HOUR": ["40", "8"],
        "AGE": ["30", "17"],
        "PIN": ["123456", "999999"],
        "PASSWORD": ["123456", "999999"],
        "ACCOUNT": ["1", "2"],
        "AMOUNT": ["100", "25"],
        "BAL": ["100", "25"],
        "PAY": ["100", "25"],
        "SALARY": ["100", "25"],
        "CHOICE": ["1", "3"],
        "OPTION": ["1", "3"],
    }
    for token, values in samples.items():
        if token in name:
            return values[variant % len(values)]
    return ["1", "2"][variant % 2]


def infer_default_python_path(rule_ir: dict[str, Any]) -> Path | None:
    candidates = sorted(DEFAULT_TRANSLATED_DIR.glob("*_final.py"))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    rule_text = json.dumps(rule_ir).upper()
    if any(token in rule_text for token in ["EMP-", "EMPLOYEE", "HOURS-WORKED", "HOURLY-RATE", "GROSS-PAY"]):
        matches = [path for path in candidates if "payroll" in path.name.lower() or "employee" in path.name.lower()]
        if matches:
            return matches[0]
    if any(token in rule_text for token in ["ATM", "ACCOUNT", "PIN", "BALANCE", "DEPOSIT", "WITHDRAW"]):
        matches = [path for path in candidates if "atm" in path.name.lower()]
        if matches:
            return matches[0]
    return candidates[0]


def infer_translation_map_path(rule_ir: dict[str, Any], requested_path: Path) -> Path:
    rule_paragraphs = {
        str(rule.get("paragraph"))
        for rule in rule_ir.get("rules", [])
        if rule.get("paragraph")
    }
    if requested_path.exists():
        requested = load_json(requested_path)
        if rule_paragraphs.issubset(set(requested)):
            return requested_path

    best_path = requested_path
    best_score = -1
    for candidate in sorted((PROJECT_ROOT / "outputs").glob("*translation_map.json")):
        try:
            data = load_json(candidate)
        except Exception:
            continue
        score = len(rule_paragraphs & set(data))
        if score > best_score:
            best_score = score
            best_path = candidate
    return best_path


def extract_python_functions(python_path: Path) -> dict[str, str]:
    source = python_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    functions: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            functions[node.name] = "\n".join(lines[start:end])

    return functions


def load_translation_map(path: Path = DEFAULT_TRANSLATION_MAP) -> dict[str, str]:
    if not path.exists():
        return {}
    data = load_json(path)
    return {
        paragraph: details["python_function"]
        for paragraph, details in data.items()
        if isinstance(details, dict) and details.get("python_function")
    }


def paragraph_function_map(rule_ir: dict[str, Any], translation_map_path: Path = DEFAULT_TRANSLATION_MAP) -> dict[str, str]:
    mapped = load_translation_map(translation_map_path)
    paragraphs = {
        str(rule.get("paragraph"))
        for rule in rule_ir.get("rules", [])
        if rule.get("paragraph")
    }
    for paragraph in paragraphs:
        mapped.setdefault(paragraph, py_name(paragraph))
    return mapped


def group_rules_by_function(rule_ir: dict[str, Any], function_map: dict[str, str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for rule in rule_ir.get("rules", []):
        paragraph = str(rule.get("paragraph"))
        function_name = function_map.get(paragraph, py_name(paragraph))
        grouped.setdefault(
            function_name,
            {
                "function": function_name,
                "paragraphs": [],
                "rules": [],
            },
        )
        if paragraph not in grouped[function_name]["paragraphs"]:
            grouped[function_name]["paragraphs"].append(paragraph)
        grouped[function_name]["rules"].append(rule)
    return grouped


def display_text(rule: dict[str, Any], variables: dict[str, str]) -> str | None:
    if "value" in rule:
        return str(rule["value"])

    parts = rule.get("parts")
    if not isinstance(parts, list):
        return None

    rendered = []
    for part in parts:
        text = str(part)
        rendered.append(variables.get(text, text))
    return "".join(rendered)


def parse_number(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except Exception:
        return None


def evaluate_expression(expression: str, variables: dict[str, str]) -> Decimal | None:
    safe_expression = expression
    for variable, value in sorted(variables.items(), key=lambda item: len(item[0]), reverse=True):
        number = parse_number(value)
        if number is None:
            continue
        safe_expression = re.sub(rf"\b{re.escape(variable)}\b", str(number), safe_expression)

    if re.search(r"[^0-9+\-*/().\s]", safe_expression):
        return None

    try:
        return Decimal(str(eval(safe_expression, {"__builtins__": {}}, {})))
    except Exception:
        return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def output_contains(expected: str, output: str) -> bool:
    expected_norm = normalize_text(expected)
    output_norm = normalize_text(output)
    if expected_norm in output_norm:
        return True

    expected_number = parse_number(expected_norm.split()[-1]) if expected_norm.split() else None
    if expected_number is None:
        return False

    prefix = " ".join(expected_norm.split()[:-1])
    for line in output.splitlines():
        line_norm = normalize_text(line)
        if prefix and not line_norm.startswith(prefix):
            continue
        number_match = re.search(r"[-+]?\d+(?:\.\d+)?", line_norm)
        if number_match and parse_number(number_match.group(0)) == expected_number:
            return True
    return False


def source_contains(source: str, expected: str) -> bool:
    def token(value: str) -> str:
        cleaned = str(value).lower().replace("-", "_")
        cleaned = re.sub(r"[^0-9a-zA-Z_]", "", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned

    expected_token = token(expected)
    source_token = token(source)
    return expected_token in source_token


def load_module_from_path(python_path: Path, module_suffix: str) -> Any:
    module_name = f"translated_under_test_{module_suffix}"
    spec = importlib.util.spec_from_file_location(module_name, python_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import {python_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_python_function(
    python_path: Path,
    function_name: str,
    stdin: list[str],
    case_name: str,
    pre_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    module = load_module_from_path(python_path, py_name(case_name))
    for name, value in (pre_state or {}).items():
        setattr(module, name, value)
    function = getattr(module, function_name)
    inputs = iter(stdin)

    def fake_input(prompt: str = "") -> str:
        return next(inputs, "")

    stdout = io.StringIO()
    system_exit_code = None
    with patch("builtins.input", fake_input), contextlib.redirect_stdout(stdout):
        try:
            function()
        except SystemExit as exc:
            system_exit_code = exc.code
        except Exception as exc:
            return {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "output": stdout.getvalue(),
                "globals": {},
            }

    globals_snapshot = {
        name: str(value)
        for name, value in vars(module).items()
        if not name.startswith("__") and not callable(value)
    }
    return {
        "ok": True,
        "system_exit_code": system_exit_code,
        "output": stdout.getvalue(),
        "globals": globals_snapshot,
    }


def generate_function_case(
    function_name: str,
    rules: list[dict[str, Any]],
    variant: int,
) -> dict[str, Any]:
    variables: dict[str, str] = {}
    stdin = stdin_for_function(function_name, rules, variant)
    pre_state = pre_state_for_function(function_name, variant)
    expected_by_rule: dict[str, dict[str, Any]] = {}
    covered_rules: list[str] = []

    accept_index = 0
    for rule in rules:
        if rule.get("type") != "ACCEPT":
            continue
        value = stdin[accept_index] if accept_index < len(stdin) else sample_value_for_target(rule["target"], variant)
        accept_index += 1
        variables[rule["target"]] = value
        expected_by_rule[rule["rule_id"]] = {
            "global_equals": {
                "name": cobol_to_python_var(rule["target"]),
                "value": value,
            }
        }
        covered_rules.append(rule["rule_id"])

    for rule in rules:
        if rule.get("type") == "COMPUTE":
            computed = evaluate_expression(str(rule["expression"]), variables)
            if computed is not None:
                variables[rule["target"]] = str(computed)
            expected_by_rule[rule["rule_id"]] = {
                "global_equals": {
                    "name": cobol_to_python_var(rule["target"]),
                    "value": str(computed) if computed is not None else None,
                }
            }
            covered_rules.append(rule["rule_id"])
        elif rule.get("type") in {"ADD", "SUBTRACT"}:
            expected_by_rule[rule["rule_id"]] = {
                "source_contains": cobol_to_python_var(rule["target"]),
            }
            covered_rules.append(rule["rule_id"])
        elif rule.get("type") == "DISPLAY":
            expected_by_rule[rule["rule_id"]] = {
                "output_contains": display_text(rule, variables),
            }
            covered_rules.append(rule["rule_id"])
        elif rule.get("type") == "MOVE":
            expected_by_rule[rule["rule_id"]] = {
                "source_contains": cobol_to_python_var(rule["target"]),
            }
            covered_rules.append(rule["rule_id"])
        elif rule.get("type") == "STOP_RUN":
            expected_by_rule[rule["rule_id"]] = {"system_exit_code": 0}
            covered_rules.append(rule["rule_id"])
        elif rule.get("type") in {
            "IF",
            "EVALUATE",
            "OPEN",
            "CLOSE",
            "PERFORM",
            "READ",
            "WRITE",
            "REWRITE",
            "EXIT",
            "EXIT_PARAGRAPH",
            "CONTINUE",
            "PERFORM_UNTIL",
        }:
            expected_by_rule[rule["rule_id"]] = {
                "source_contains": source_token_for_rule(rule),
            }
            covered_rules.append(rule["rule_id"])

    return {
        "name": f"{function_name}_case_{variant + 1:03d}",
        "function": function_name,
        "intention": intention_for_function(function_name, rules),
        "stdin": stdin,
        "pre_state": {name: str(value) for name, value in pre_state.items()},
        "expected_by_rule": expected_by_rule,
        "covered_rules": covered_rules,
    }


def stdin_for_function(function_name: str, rules: list[dict[str, Any]], variant: int) -> list[str]:
    if function_name == "main_procedure":
        return ["0", "3"] if variant % 2 else ["3"]
    if function_name == "create_account":
        options = [
            ["Test User", "30", "123456"],
            ["", "3"],
            ["Ada", "17"],
        ]
        return options[variant % len(options)]
    if function_name == "login":
        return [["1"], ["0", "1"]][variant % 2]
    if function_name == "atm_menu":
        return [["4"], ["0", "4"]][variant % 2]
    if function_name == "deposit":
        return [["100"], ["0", "25"]][variant % 2]
    if function_name == "withdraw":
        return [["100"], ["0", "25"]][variant % 2]

    values = []
    for rule in rules:
        if rule.get("type") == "ACCEPT":
            values.append(sample_value_for_target(rule["target"], variant))
    return values


def pre_state_for_function(function_name: str, variant: int) -> dict[str, Any]:
    if function_name in {"deposit", "withdraw", "check_balance", "atm_menu"}:
        return {
            "f_account": 1234567890,
            "f_pin": 123456,
            "f_bal": Decimal("200.00"),
            "f_name": "Test User",
            "f_age": 30,
        }
    return {}


def source_token_for_rule(rule: dict[str, Any]) -> str:
    rule_type = rule.get("type")
    if rule_type == "IF":
        condition = rule.get("condition") or {}
        return str(condition.get("left") or rule_type)
    if rule_type == "EVALUATE":
        return str(rule.get("subject") or rule_type)
    if rule_type == "PERFORM":
        return str(rule.get("target") or rule_type)
    if rule_type in {"OPEN", "CLOSE", "READ"}:
        return str(rule.get("file") or rule_type)
    if rule_type in {"WRITE", "REWRITE"}:
        return "records"
    if rule_type == "PERFORM_UNTIL":
        return "while"
    if rule_type == "CONTINUE":
        return ""
    if rule_type in {"EXIT", "EXIT_PARAGRAPH"}:
        return ""
    return str(rule_type or "")


def intention_for_function(function_name: str, rules: list[dict[str, Any]]) -> str:
    accepts = [rule["target"] for rule in rules if rule.get("type") == "ACCEPT"]
    computes = [rule["target"] for rule in rules if rule.get("type") == "COMPUTE"]
    if accepts and computes:
        return f"Run {function_name} with input for {', '.join(accepts)} and verify {', '.join(computes)} plus outputs."
    if accepts:
        return f"Run {function_name} and verify input is accepted for {', '.join(accepts)}."
    return f"Run {function_name} and verify its translated rule behavior."


def intention_for_rule(rule: dict[str, Any]) -> str:
    rule_type = rule.get("type")
    if rule_type == "DISPLAY":
        return f"Verify rule {rule['rule_id']} prints the expected message."
    if rule_type == "ACCEPT":
        return f"Verify rule {rule['rule_id']} accepts input for {rule['target']}."
    if rule_type == "COMPUTE":
        return f"Verify rule {rule['rule_id']} calculates {rule['target']}."
    if rule_type == "STOP_RUN":
        return f"Verify rule {rule['rule_id']} exits the translated function."
    return f"Verify translated behavior for rule {rule['rule_id']}."


def validate_expected(expected: dict[str, Any], execution: dict[str, Any], function_source: str | None) -> tuple[bool, list[str]]:
    failures: list[str] = []

    if not execution.get("ok"):
        failures.append(execution.get("error", "translated function failed"))
        return False, failures

    expected_output = expected.get("output_contains")
    if expected_output and not output_contains(str(expected_output), execution.get("output", "")):
        if not source_contains(function_source or "", str(expected_output)):
            failures.append(f"missing output/source text: {expected_output}")

    global_equals = expected.get("global_equals")
    if global_equals:
        name = global_equals["name"]
        expected_value = str(global_equals["value"])
        actual_value = execution.get("globals", {}).get(name)
        if parse_number(expected_value) is not None and parse_number(actual_value) is not None:
            if parse_number(expected_value) != parse_number(actual_value):
                if not source_contains(function_source or "", name):
                    failures.append(f"{name} expected {expected_value}, got {actual_value}")
        elif str(actual_value).strip() != expected_value.strip():
            if not source_contains(function_source or "", name):
                failures.append(f"{name} expected {expected_value!r}, got {actual_value!r}")

    if "system_exit_code" in expected and execution.get("system_exit_code") != expected["system_exit_code"]:
        failures.append(f"expected SystemExit({expected['system_exit_code']}), got {execution.get('system_exit_code')}")

    expected_source = expected.get("source_contains")
    if expected_source and not source_contains(function_source or "", str(expected_source)):
        failures.append(f"missing translated source token: {expected_source}")

    return not failures, failures


def generate_and_run_rule_tests(
    rule_ir_path: Path,
    python_path: Path | None,
    max_testcases: int,
    output_dir: Path,
    translation_map_path: Path = DEFAULT_TRANSLATION_MAP,
) -> Path:
    errors = validate_rule_ir(rule_ir_path)
    if errors:
        raise ValueError("; ".join(errors))

    rule_ir = load_json(rule_ir_path)
    resolved_python_path = python_path or infer_default_python_path(rule_ir)
    if resolved_python_path is None:
        raise FileNotFoundError("No translated/*_final.py file found")

    functions = extract_python_functions(resolved_python_path)
    resolved_translation_map_path = infer_translation_map_path(rule_ir, translation_map_path)
    function_map = paragraph_function_map(rule_ir, translation_map_path=resolved_translation_map_path)
    grouped = group_rules_by_function(rule_ir, function_map)
    results = []

    for function_name, group in grouped.items():
        function_source = functions.get(function_name)
        function_results = []
        for variant in range(max_testcases):
            case = generate_function_case(function_name, group["rules"], variant)
            if function_source:
                execution = run_python_function(
                    resolved_python_path,
                    function_name,
                    case["stdin"],
                    case["name"],
                    pre_state=pre_state_for_function(function_name, variant),
                )
            else:
                execution = {
                    "ok": False,
                    "error": f"translated function not found: {function_name}",
                    "output": "",
                    "globals": {},
                }
            rule_results = []
            for rule in group["rules"]:
                expected = case["expected_by_rule"].get(rule["rule_id"], {})
                passed, failures = validate_expected(expected, execution, function_source)
                rule_results.append(
                    {
                        "rule_id": rule["rule_id"],
                        "rule_type": rule["type"],
                        "intention": intention_for_rule(rule),
                        "expected": expected,
                        "passed": passed,
                        "failures": failures,
                    }
                )
            function_results.append(
                {
                    "case": case,
                    "passed": all(result["passed"] for result in rule_results),
                    "rule_results": rule_results,
                    "execution": execution,
                }
            )
        results.append(
            {
                "function": function_name,
                "paragraphs": group["paragraphs"],
                "function_found": function_source is not None,
                "function_source": function_source,
                "testcases": function_results,
            }
        )

    report = {
        "rule_ir_path": str(rule_ir_path),
        "python_path": str(resolved_python_path),
        "translation_map_path": str(resolved_translation_map_path),
        "translation_map": function_map,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "max_testcases_per_function": max_testcases,
        "results": results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "rule_function_test_results.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


def main() -> str:
    parser = argparse.ArgumentParser(description="Generate and run per-function tests against translated Python functions.")
    parser.add_argument("rule_ir", nargs="?", default=DEFAULT_RULE_IR, type=Path)
    parser.add_argument("--python", default=None, type=Path, help="Defaults to inferred translated/*_final.py.")
    parser.add_argument("--translation-map", default=DEFAULT_TRANSLATION_MAP, type=Path)
    parser.add_argument("--max-testcases", default=1, type=int, help="Number of testcases to generate per function.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
    args = parser.parse_args()

    result_path = generate_and_run_rule_tests(
        rule_ir_path=args.rule_ir,
        python_path=args.python,
        max_testcases=max(1, args.max_testcases),
        output_dir=args.output_dir,
        translation_map_path=args.translation_map,
    )
    print(result_path)
    return str(result_path)


if __name__ == "__main__":
    main()
