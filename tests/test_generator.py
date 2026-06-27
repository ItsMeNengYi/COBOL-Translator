from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class CobolAction:
    section: str
    choice: str
    label: str


@dataclass
class CobolPrompt:
    variable: str
    prompt: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def strip_cobol_sequence_area(line: str) -> str:
    if len(line) > 6 and line[:6].strip().isdigit():
        return line[6:].strip()
    return line.strip()


def discover_actions(cobol_source: str) -> list[CobolAction]:
    actions: list[CobolAction] = []
    section = "program"

    for raw_line in cobol_source.splitlines():
        line = strip_cobol_sequence_area(raw_line)
        upper = line.upper()

        if re.match(r"^[A-Z0-9-]+\.$", upper):
            section = upper[:-1].lower()

        match = re.match(r'DISPLAY\s+"(\d+)\s*[-.)]\s*([^"]+)"', line, re.IGNORECASE)
        if match:
            actions.append(
                CobolAction(
                    section=section,
                    choice=match.group(1),
                    label=match.group(2).strip(),
                )
            )

    return actions


def discover_accept_prompts(cobol_source: str) -> list[CobolPrompt]:
    prompts: list[CobolPrompt] = []
    previous_display = ""

    for raw_line in cobol_source.splitlines():
        line = strip_cobol_sequence_area(raw_line)
        display = re.match(r'DISPLAY\s+"([^"]+)"', line, re.IGNORECASE)
        if display:
            previous_display = display.group(1).strip()
            continue

        accept = re.match(r"ACCEPT\s+([A-Z0-9-]+)", line, re.IGNORECASE)
        if accept:
            prompts.append(
                CobolPrompt(
                    variable=accept.group(1).upper(),
                    prompt=previous_display,
                )
            )

    return prompts


def sample_value_for_prompt(prompt: CobolPrompt) -> str:
    text = f"{prompt.prompt} {prompt.variable}".upper()

    if "NAME" in text:
        return "Test User"
    if "AGE" in text:
        return "30"
    if "PIN" in text or "PASSWORD" in text:
        return "123456"
    if "ACCOUNT" in text:
        return "1"
    if "AMOUNT" in text or "BALANCE" in text or "SALARY" in text:
        return "100"
    if "DATE" in text:
        return "2026-01-01"
    if "YES" in text or "Y/N" in text:
        return "Y"
    if "CHOICE" in text or "OPTION" in text or "MENU" in text:
        return "1"
    return "1"


def deterministic_stdin_arrays(actions: list[CobolAction], prompts: list[CobolPrompt]) -> list[list[str]]:
    stdin_arrays: list[list[str]] = []
    sample_values = [sample_value_for_prompt(prompt) for prompt in prompts]
    entry_section = actions[0].section if actions else None
    entry_actions = [action for action in actions if action.section == entry_section]
    exit_action = next(
        (action for action in entry_actions if action.label.upper() in {"EXIT", "QUIT"}),
        None,
    )

    if entry_actions:
        for action in entry_actions:
            stdin = [action.choice]
            if action != exit_action:
                stdin.extend(sample_values)
            if exit_action and action != exit_action:
                stdin.append(exit_action.choice)
            stdin_arrays.append(stdin)

        if exit_action:
            stdin_arrays.append(["0", exit_action.choice])

    if prompts:
        stdin = list(sample_values)
        if exit_action:
            stdin.append(exit_action.choice)
        stdin_arrays.append(stdin)

    return unique_stdin_arrays(stdin_arrays)


def unique_stdin_arrays(stdin_arrays: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []

    for stdin in stdin_arrays:
        key = tuple(stdin)
        if key not in seen:
            seen.add(key)
            unique.append(stdin)

    return unique


def extract_json_array(text: str) -> list[list[str]]:
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    stdin_arrays: list[list[str]] = []
    for item in parsed:
        if isinstance(item, list):
            stdin_arrays.append([str(value) for value in item])
        elif isinstance(item, dict) and isinstance(item.get("stdin"), list):
            stdin_arrays.append([str(value) for value in item["stdin"]])

    return unique_stdin_arrays(stdin_arrays)


def ai_stdin_arrays(cobol_source: str, max_cases: int) -> list[list[str]]:
    from src.llm_agent import OpenAIAgent

    agent = OpenAIAgent(
        system_prompt=(
            "You generate stdin test cases for interactive COBOL programs. "
            "Return only valid JSON: an array of arrays of strings. "
            "Each inner array is one complete stdin sequence."
        )
    )
    response = agent.chat(
        "Analyze this COBOL program and generate up to "
        f"{max_cases} stdin test cases that cover normal and validation paths.\n\n"
        f"{cobol_source}"
    )
    return extract_json_array(response)[:max_cases]


def generate_stdin_arrays(cobol_path: str | Path, use_ai: bool = False, max_cases: int = 10) -> dict[str, Any]:
    cobol_path = Path(cobol_path)
    cobol_source = read_text(cobol_path)
    actions = discover_actions(cobol_source)
    prompts = discover_accept_prompts(cobol_source)

    stdin_arrays = deterministic_stdin_arrays(actions, prompts)
    method = "deterministic"

    if use_ai and len(stdin_arrays) < 2:
        ai_arrays = ai_stdin_arrays(cobol_source, max_cases=max_cases)
        if ai_arrays:
            stdin_arrays = ai_arrays
            method = "ai"

    if not stdin_arrays:
        stdin_arrays = [["1"]]
        method = "fallback"

    return {
        "method": method,
        "actions": [asdict(action) for action in actions],
        "prompts": [asdict(prompt) for prompt in prompts],
        "stdin_arrays": stdin_arrays[:max_cases],
    }


def build_test_json(
    cobol_path: str | Path,
    python_path: str | Path,
    stdin_arrays: list[list[str]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "cobol_path": str(cobol_path),
        "python_path": str(python_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "metadata": metadata or {},
        "tests": [
            {
                "name": f"case_{index:03d}",
                "stdin": stdin,
            }
            for index, stdin in enumerate(stdin_arrays, start=1)
        ],
    }


def save_timestamped_test_json(report: dict[str, Any], folder: Path | None = None) -> Path:
    output_folder = folder or Path(__file__).resolve().parent
    output_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_folder / f"generated_tests_{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


def generate_and_save_test_json(
    cobol_path: str | Path,
    python_path: str | Path,
    use_ai: bool = False,
    max_cases: int = 10,
) -> Path:
    generated = generate_stdin_arrays(cobol_path, use_ai=use_ai, max_cases=max_cases)
    report = build_test_json(
        cobol_path=cobol_path,
        python_path=python_path,
        stdin_arrays=generated["stdin_arrays"],
        metadata={
            "method": generated["method"],
            "actions": generated["actions"],
            "prompts": generated["prompts"],
        },
    )
    return save_timestamped_test_json(report)


def command_output(command: list[str], stdin: list[str], cwd: Path, timeout: int = 15) -> dict[str, Any]:
    stdin_text = "\n".join(stdin) + "\n"

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            input=stdin_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "output": completed.stdout.decode("utf-8", errors="replace"),
        }
    except FileNotFoundError as exc:
        return {
            "returncode": None,
            "error": str(exc),
            "output": "",
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode("utf-8", errors="replace")
        return {
            "returncode": None,
            "error": "timeout",
            "output": output,
        }


def compile_cobol(cobol_path: str | Path, build_dir: Path) -> dict[str, Any]:
    cobol_path = Path(cobol_path)
    if not shutil.which("cobc"):
        return {
            "ok": False,
            "error": "cobc not found on PATH",
            "executable": None,
            "output": "",
        }

    executable = build_dir / cobol_path.stem
    completed = subprocess.run(
        ["cobc", "-x", "-free", str(cobol_path.resolve()), "-o", str(executable)],
        cwd=build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    output = completed.stdout.decode("utf-8", errors="replace")

    return {
        "ok": completed.returncode == 0 and executable.exists(),
        "returncode": completed.returncode,
        "executable": str(executable) if executable.exists() else None,
        "output": output,
    }


def output_diff(cobol_output: str, python_output: str) -> str:
    cobol_output = normalize_dynamic_output(cobol_output)
    python_output = normalize_dynamic_output(python_output)
    return "".join(
        difflib.unified_diff(
            cobol_output.splitlines(keepends=True),
            python_output.splitlines(keepends=True),
            fromfile="cobol",
            tofile="python",
        )
    )


def normalize_dynamic_output(output: str) -> str:
    """Normalize values that are intentionally nondeterministic across runs."""
    lines = output.splitlines()
    normalized: list[str] = []
    previous = ""

    for line in lines:
        if previous.strip().upper() == "YOUR ACCOUNT NUMBER IS:" and re.fullmatch(r"\d{10}", line.strip()):
            normalized.append("<ACCOUNT_NUMBER>")
        else:
            normalized.append(line)
        previous = line

    return "\n".join(normalized) + ("\n" if output.endswith("\n") else "")


def run_testcases(
    cobol_path: str | Path,
    python_path: str | Path,
    stdin_arrays: list[list[str]],
) -> dict[str, Any]:
    python_path = Path(python_path)

    with tempfile.TemporaryDirectory(prefix="cobol-test-run-") as temp_name:
        temp_dir = Path(temp_name)
        compile_result = compile_cobol(cobol_path, temp_dir)

        results = []
        for index, stdin in enumerate(stdin_arrays, start=1):
            case_dir = temp_dir / f"case_{index:03d}"
            cobol_dir = case_dir / "cobol"
            python_dir = case_dir / "python"
            cobol_dir.mkdir(parents=True, exist_ok=True)
            python_dir.mkdir(parents=True, exist_ok=True)

            if compile_result["ok"]:
                cobol_result = command_output([compile_result["executable"]], stdin, cobol_dir)
            else:
                cobol_result = {
                    "returncode": None,
                    "error": "COBOL compile failed",
                    "output": compile_result.get("output", ""),
                }

            python_result = command_output([sys.executable, str(python_path.resolve())], stdin, python_dir)
            diff = output_diff(cobol_result["output"], python_result["output"])

            results.append(
                {
                    "name": f"case_{index:03d}",
                    "stdin": stdin,
                    "matched": diff == "",
                    "cobol": cobol_result,
                    "python": python_result,
                    "diff": diff,
                }
            )

    return {
        "cobol_path": str(cobol_path),
        "python_path": str(python_path),
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "compile": compile_result,
        "results": results,
    }


def run_testcases_from_json(test_json_path: str | Path) -> dict[str, Any]:
    test_json_path = Path(test_json_path)
    if not test_json_path.exists():
        raise FileNotFoundError(f"Test JSON does not exist: {test_json_path}")

    test_json = json.loads(test_json_path.read_text(encoding="utf-8"))
    stdin_arrays = [[str(value) for value in test["stdin"]] for test in test_json["tests"]]
    return run_testcases(
        cobol_path=test_json["cobol_path"],
        python_path=test_json["python_path"],
        stdin_arrays=stdin_arrays,
    )


def save_timestamped_result_json(report: dict[str, Any], folder: Path | None = None) -> Path:
    output_folder = folder or Path(__file__).resolve().parent
    output_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_folder / f"test_results_{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and run stdin tests for a COBOL/Python pair.")
    parser.add_argument("test_json", nargs="?", type=Path, help="Optional generated_tests_*.json to run.")
    parser.add_argument("--cobol", default="inputs/ATM.cob", type=Path)
    parser.add_argument("--python", default="translated/atm_translated_final.py", type=Path)
    parser.add_argument("--use-ai", action="store_true", help="Ask llm_agent.py if deterministic analysis is weak.")
    parser.add_argument("--max-cases", default=10, type=int)
    parser.add_argument("--run-json", type=Path, help="Run an existing generated_tests_*.json file.")
    parser.add_argument("--generate-only", action="store_true", help="Only generate test JSON; do not run it.")
    parser.add_argument(
        "--run-after-generate",
        action="store_true",
        help="Deprecated: generation now runs by default unless --generate-only is used.",
    )
    args = parser.parse_args()

    run_json_path = args.run_json or args.test_json
    if run_json_path:
        try:
            result = run_testcases_from_json(run_json_path)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        output_path = save_timestamped_result_json(result)
        print(f"Wrote {output_path}")
        return

    output_path = generate_and_save_test_json(
        cobol_path=args.cobol,
        python_path=args.python,
        use_ai=args.use_ai,
        max_cases=args.max_cases,
    )
    print(f"Wrote {output_path}")

    if args.generate_only:
        return

    result = run_testcases_from_json(output_path)
    result_path = save_timestamped_result_json(result)
    print(f"Wrote {result_path}")

    return result_path

if __name__ == "__main__":
    main()
