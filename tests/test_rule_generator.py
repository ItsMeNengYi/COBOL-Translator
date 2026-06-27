import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULE_IR = PROJECT_ROOT / "outputs" / "rule_ir.json"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_TRANSLATED_DIR = PROJECT_ROOT / "translated"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_default_python_path(rule_ir: dict[str, Any]) -> Path | None:
    candidates = sorted(DEFAULT_TRANSLATED_DIR.glob("*_final.py"))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    rule_text = json.dumps(rule_ir).upper()
    if any(token in rule_text for token in ["EMP-", "EMPLOYEE", "HOURS-WORKED", "HOURLY-RATE", "GROSS-PAY"]):
        payroll_matches = [path for path in candidates if "payroll" in path.name.lower() or "employee" in path.name.lower()]
        if payroll_matches:
            return payroll_matches[0]

    if any(token in rule_text for token in ["ATM", "ACCOUNT", "PIN", "BALANCE", "DEPOSIT", "WITHDRAW"]):
        atm_matches = [path for path in candidates if "atm" in path.name.lower()]
        if atm_matches:
            return atm_matches[0]

    return candidates[0]


def sample_value_for_target(target: str) -> str:
    name = target.upper()

    if "NAME" in name:
        return "Test User"
    if "RATE" in name:
        return "25"
    if "HOUR" in name:
        return "40"
    if "AGE" in name:
        return "30"
    if "PIN" in name or "PASSWORD" in name:
        return "123456"
    if "ACCOUNT" in name:
        return "1"
    if "AMOUNT" in name or "BAL" in name or "PAY" in name or "SALARY" in name:
        return "100"
    if "DATE" in name:
        return "2026-01-01"
    if "CHOICE" in name or "OPTION" in name:
        return "1"
    return "1"


def parse_number(value: str) -> int | float | None:
    try:
        number = float(value)
    except ValueError:
        return None

    if number.is_integer():
        return int(number)
    return number


def evaluate_expression(expression: str, variables: dict[str, str]) -> str | None:
    safe_expression = expression
    for variable, value in sorted(variables.items(), key=lambda item: len(item[0]), reverse=True):
        number = parse_number(value)
        if number is None:
            continue
        safe_expression = re.sub(rf"\b{re.escape(variable)}\b", str(number), safe_expression)

    if re.search(r"[^0-9+\-*/().\s]", safe_expression):
        return None

    try:
        result = eval(safe_expression, {"__builtins__": {}}, {})
    except Exception:
        return None

    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


def display_text(rule: dict[str, Any], variables: dict[str, str]) -> str | None:
    if "value" in rule:
        return str(rule["value"])

    parts = rule.get("parts")
    if not isinstance(parts, list):
        return None

    rendered_parts: list[str] = []
    for part in parts:
        part_text = str(part)
        rendered_parts.append(variables.get(part_text, part_text))
    return "".join(rendered_parts)


def build_intention(covered_rules: list[str], accepts: list[dict[str, Any]], computes: list[dict[str, Any]]) -> str:
    if accepts and computes:
        accepted_names = ", ".join(rule["target"] for rule in accepts)
        computed_names = ", ".join(rule["target"] for rule in computes)
        return f"Enter {accepted_names} and verify {computed_names} is calculated and displayed."
    if accepts:
        accepted_names = ", ".join(rule["target"] for rule in accepts)
        return f"Enter values for {accepted_names} and verify the program accepts the input."
    if computes:
        computed_names = ", ".join(rule["target"] for rule in computes)
        return f"Verify calculation rules for {computed_names}."
    return f"Cover rules {', '.join(covered_rules)}."


def generate_rule_testcases(rule_ir: dict[str, Any]) -> list[dict[str, Any]]:
    rules = rule_ir.get("rules") or []
    accepts = [rule for rule in rules if rule.get("type") == "ACCEPT"]
    computes = [rule for rule in rules if rule.get("type") == "COMPUTE"]

    variables: dict[str, str] = {}
    stdin: list[str] = []
    covered_rules: list[str] = []

    for rule in accepts:
        target = rule["target"]
        value = sample_value_for_target(target)
        variables[target] = value
        stdin.append(value)
        covered_rules.append(rule["rule_id"])

    expected_outputs: list[str] = []
    for rule in rules:
        if rule.get("type") == "COMPUTE":
            result = evaluate_expression(str(rule["expression"]), variables)
            if result is not None:
                variables[rule["target"]] = result
            covered_rules.append(rule["rule_id"])

        if rule.get("type") == "DISPLAY":
            output = display_text(rule, variables)
            if output:
                expected_outputs.append(output)
            covered_rules.append(rule["rule_id"])

        if rule.get("type") == "STOP_RUN":
            covered_rules.append(rule["rule_id"])

    return [
        {
            "name": "rule_case_001",
            "intention": build_intention(covered_rules, accepts, computes),
            "stdin": stdin,
            "expected_outputs": expected_outputs,
            "covered_rules": sorted(set(covered_rules)),
        }
    ]


def build_rule_test_json(
    rule_ir_path: str | Path = DEFAULT_RULE_IR,
    python_path: str | Path | None = None,
) -> dict[str, Any]:
    rule_ir_path = Path(rule_ir_path)
    rule_ir = load_json(rule_ir_path)
    resolved_python_path = Path(python_path) if python_path else infer_default_python_path(rule_ir)

    return {
        "rule_ir_path": str(rule_ir_path),
        "python_path": str(resolved_python_path) if resolved_python_path else None,
        "program": rule_ir.get("program"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "rule_ir",
        "tests": generate_rule_testcases(rule_ir),
    }


def save_rule_test_json(report: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_dir / f"rule_generated_tests_{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


def run_python_rule_tests(report: dict[str, Any]) -> dict[str, Any]:
    python_path = report.get("python_path")
    if not python_path:
        raise ValueError("python_path is required to run generated rule tests")

    results = []
    for test in report["tests"]:
        stdin_text = "\n".join(test["stdin"]) + "\n"
        completed = subprocess.run(
            [sys.executable, str(Path(python_path).resolve())],
            input=stdin_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
        output = completed.stdout.decode("utf-8", errors="replace")
        missing_outputs = [
            expected
            for expected in test.get("expected_outputs", [])
            if expected not in output
        ]
        results.append(
            {
                "name": test["name"],
                "intention": test["intention"],
                "stdin": test["stdin"],
                "returncode": completed.returncode,
                "passed": completed.returncode == 0 and not missing_outputs,
                "missing_outputs": missing_outputs,
                "output": output,
            }
        )

    return {
        "rule_ir_path": report["rule_ir_path"],
        "python_path": python_path,
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }


def save_rule_result_json(report: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_dir / f"rule_test_results_{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate simple test cases from outputs/rule_ir.json.")
    parser.add_argument("--rule-ir", default=DEFAULT_RULE_IR, type=Path)
    parser.add_argument("--python", default=None, type=Path, help="Defaults to an inferred translated/*_final.py file.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
    parser.add_argument("--run-python", action="store_true")
    args = parser.parse_args()

    report = build_rule_test_json(rule_ir_path=args.rule_ir, python_path=args.python)
    output_path = save_rule_test_json(report, output_dir=args.output_dir)
    print(f"Wrote {output_path}")

    if args.run_python:
        result = run_python_rule_tests(report)
        result_path = save_rule_result_json(result, output_dir=args.output_dir)
        print(f"Wrote {result_path}")


if __name__ == "__main__":
    main()
