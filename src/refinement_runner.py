"""Automated refinement loop for generated COBOL-to-Python translations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_GENERATOR_PATH = ROOT_DIR / "tests" / "test_generator.py"


def _load_test_generator():
    spec = importlib.util.spec_from_file_location("cobol_test_generator", TEST_GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load test generator from {TEST_GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _program_stem(cobol_path: str | Path) -> str:
    return Path(cobol_path).stem.lower()


def _translated_dir(cobol_path: str | Path) -> Path:
    return ROOT_DIR / "translated" / _program_stem(cobol_path)


def _pipeline_final_path(cobol_path: str | Path) -> Path:
    return _translated_dir(cobol_path) / "translated_final.py"


def _version_path(cobol_path: str | Path, iteration: int) -> Path:
    stem = _program_stem(cobol_path)
    return _translated_dir(cobol_path) / f"{stem}_v{iteration}.py"


def _best_path(cobol_path: str | Path) -> Path:
    stem = _program_stem(cobol_path)
    return _translated_dir(cobol_path) / f"{stem}_best.py"


def _report_path(cobol_path: str | Path) -> Path:
    return _translated_dir(cobol_path) / "refinement_report.json"


def _tests_path(cobol_path: str | Path) -> Path:
    return _translated_dir(cobol_path) / "generated_tests.json"


def _run_pipeline(cobol_path: str | Path) -> Path:
    command = [sys.executable, "-m", "src.pipeline", str(cobol_path)]
    subprocess.run(command, cwd=ROOT_DIR, check=True)
    final_path = _pipeline_final_path(cobol_path)
    if not final_path.exists():
        raise FileNotFoundError(f"Pipeline did not produce {final_path}")
    return final_path


def _generate_test_json(cobol_path: str | Path, python_path: str | Path, max_cases: int = 10) -> tuple[Path, list[list[str]]]:
    test_generator = _load_test_generator()
    generated = test_generator.generate_stdin_arrays(
        cobol_path=cobol_path,
        use_ai=False,
        max_cases=max_cases,
    )
    stdin_arrays = generated["stdin_arrays"]
    report = test_generator.build_test_json(
        cobol_path=cobol_path,
        python_path=python_path,
        stdin_arrays=stdin_arrays,
        metadata={
            "method": generated["method"],
            "actions": generated["actions"],
            "prompts": generated["prompts"],
        },
    )
    tests_path = _tests_path(cobol_path)
    tests_path.parent.mkdir(parents=True, exist_ok=True)
    tests_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return tests_path, stdin_arrays


def _run_tests(cobol_path: str | Path, python_path: str | Path, stdin_arrays: list[list[str]]) -> dict[str, Any]:
    test_generator = _load_test_generator()
    return test_generator.run_testcases(
        cobol_path=cobol_path,
        python_path=python_path,
        stdin_arrays=stdin_arrays,
    )


def _case_error_messages(result: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    compile_result = result.get("compile") or {}
    if not compile_result.get("ok"):
        error = compile_result.get("error") or "COBOL compile failed"
        output = str(compile_result.get("output") or "").strip()
        messages.append(f"COBOL compile: {error}{': ' + output if output else ''}")

    for case in result.get("results") or []:
        name = case.get("name", "case")
        for side in ("cobol", "python"):
            side_result = case.get(side) or {}
            if side_result.get("error"):
                messages.append(f"{name} {side}: {side_result['error']}")
            returncode = side_result.get("returncode")
            if returncode not in (0, None):
                messages.append(f"{name} {side}: return code {returncode}")
        if case.get("diff"):
            messages.append(f"{name}: output mismatch")

    return messages


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    cases = result.get("results") or []
    total = len(cases)
    passed = sum(1 for case in cases if case.get("matched") is True)
    failed = total - passed
    error_messages = _case_error_messages(result)
    runtime_errors = len([
        message for message in error_messages
        if "return code" in message or "timeout" in message or "compile" in message.lower()
    ])
    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "runtime_errors": runtime_errors,
        "error_messages": error_messages,
        "raw_result": result,
    }


def _source_quality(path: Path) -> dict[str, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return {
        "todo_count": source.count("# TODO unsupported"),
        "fallback_failure_count": source.count("fallback failed") + source.count("fallback skipped"),
        "line_count": len(source.splitlines()),
    }


def _is_better(candidate: dict[str, Any], best: dict[str, Any] | None, candidate_path: Path, best_path: Path | None) -> tuple[bool, str]:
    if best is None:
        return True, "initial version"
    if candidate["passed"] > best["passed"]:
        return True, "improved pass count"
    if candidate["passed"] < best["passed"]:
        return False, "worse pass count"
    if candidate["runtime_errors"] < best["runtime_errors"]:
        return True, "same pass count with fewer runtime/errors"
    if candidate["runtime_errors"] > best["runtime_errors"]:
        return False, "same pass count with more runtime/errors"

    if best_path is not None:
        candidate_quality = _source_quality(candidate_path)
        best_quality = _source_quality(best_path)
        if candidate_quality["todo_count"] < best_quality["todo_count"]:
            return True, "same tests with fewer unsupported TODOs"
        if (
            candidate_quality["todo_count"] == best_quality["todo_count"]
            and candidate_quality["fallback_failure_count"] < best_quality["fallback_failure_count"]
        ):
            return True, "same tests with cleaner generated code"

    return False, "no improvement"


def _apply_deterministic_refinement(candidate_path: Path, previous_failures: list[dict[str, Any]]) -> str:
    """Apply safe local repairs. Returns a short reason for the report."""
    source = candidate_path.read_text(encoding="utf-8", errors="replace")
    patched = source

    # Conservative cleanup for generated Python. More semantic repairs should
    # happen in parser/translator rules, then be validated by this loop.
    patched = patched.replace("pass  # LLM fallback skipped", "pass  # fallback skipped")

    if patched != source:
        candidate_path.write_text(patched, encoding="utf-8")
        return "applied deterministic cleanup"
    if previous_failures:
        return "no deterministic repair available for current failures"
    return "no repair needed before first evaluation"


def _status(best_summary: dict[str, Any] | None) -> str:
    if best_summary is None:
        return "failed"
    if best_summary["total_tests"] and best_summary["failed"] == 0:
        return "passed"
    if best_summary["passed"] > 0:
        return "partial"
    return "failed"


def run_refinement(
    cobol_path: str,
    max_iterations: int = 5,
    patience: int = 2,
) -> dict[str, Any]:
    """Run translate-test-refine until tests pass or stop conditions fire."""
    cobol = Path(cobol_path)
    if not cobol.is_absolute():
        cobol = ROOT_DIR / cobol
    if not cobol.exists():
        raise FileNotFoundError(f"COBOL source file not found: {cobol}")

    translated_dir = _translated_dir(cobol)
    translated_dir.mkdir(parents=True, exist_ok=True)

    initial_final = _run_pipeline(cobol)
    tests_path, stdin_arrays = _generate_test_json(cobol, initial_final)

    history: list[dict[str, Any]] = []
    best_summary: dict[str, Any] | None = None
    best_iteration = 0
    best_file = _best_path(cobol)
    previous_failures: list[dict[str, Any]] = []
    no_improvement = 0
    iterations_used = 0

    for iteration in range(1, max_iterations + 1):
        iterations_used = iteration
        candidate_file = _version_path(cobol, iteration)
        if iteration == 1:
            shutil.copyfile(initial_final, candidate_file)
            refinement_reason = "initial version"
        else:
            shutil.copyfile(best_file, candidate_file)
            refinement_reason = _apply_deterministic_refinement(candidate_file, previous_failures)

        result = _run_tests(cobol, candidate_file, stdin_arrays)
        summary = _summarize_result(result)
        accepted, keep_reason = _is_better(summary, best_summary, candidate_file, best_file if best_file.exists() else None)

        if accepted:
            shutil.copyfile(candidate_file, best_file)
            best_summary = summary
            best_iteration = iteration
            no_improvement = 0
        else:
            no_improvement += 1

        failed_cases = [
            case for case in result.get("results") or []
            if not case.get("matched")
        ]
        previous_failures = failed_cases

        history.append({
            "iteration": iteration,
            "version_file": str(candidate_file.relative_to(ROOT_DIR)),
            "total_tests": summary["total_tests"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "pass_rate": summary["pass_rate"],
            "runtime_errors": summary["runtime_errors"],
            "error_messages": summary["error_messages"],
            "kept": accepted,
            "latest_accepted": accepted,
            "latest_discarded": not accepted,
            "reason": keep_reason if iteration == 1 else f"{keep_reason}; {refinement_reason}",
        })

        if best_summary and best_summary["total_tests"] and best_summary["failed"] == 0:
            break
        if no_improvement >= patience:
            break

    final_best = best_summary or {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "pass_rate": 0.0,
        "runtime_errors": 0,
        "error_messages": ["No test run completed"],
    }
    if best_file.exists():
        shutil.copyfile(best_file, _pipeline_final_path(cobol))

    report = {
        "cobol_path": str(cobol),
        "generated_tests": str(tests_path.relative_to(ROOT_DIR)),
        "max_iterations": max_iterations,
        "patience": patience,
        "best_iteration": best_iteration,
        "total_tests": final_best["total_tests"],
        "best_passed": final_best["passed"],
        "best_failed": final_best["failed"],
        "best_pass_rate": final_best["pass_rate"],
        "best_file": str(best_file.relative_to(ROOT_DIR)),
        "iterations_used": iterations_used,
        "status": _status(best_summary),
        "history": history,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    report_path = _report_path(cobol)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return {
        "status": report["status"],
        "best_file": str(best_file.relative_to(ROOT_DIR)),
        "best_passed": final_best["passed"],
        "best_failed": final_best["failed"],
        "iterations_used": iterations_used,
        "report_path": str(report_path.relative_to(ROOT_DIR)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated translation refinement.")
    parser.add_argument("cobol_path", help="COBOL source file to refine.")
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--patience", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_refinement(
        cobol_path=args.cobol_path,
        max_iterations=args.max_iterations,
        patience=args.patience,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
