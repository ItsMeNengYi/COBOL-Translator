from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st


DEFAULT_RESULTS_PATH = Path("tests/rule_function_test_results.json")


def load_rule_function_results(path: Path = DEFAULT_RESULTS_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def summarize_rule_function_results(data: dict[str, Any] | None) -> dict[str, int]:
    results = (data or {}).get("results") or []
    total_functions = len(results)
    missing_functions = sum(1 for item in results if not item.get("function_found"))
    total_cases = 0
    passed_cases = 0
    failed_rules = 0
    total_rules = 0

    for item in results:
        for testcase in item.get("testcases") or []:
            total_cases += 1
            if testcase.get("passed"):
                passed_cases += 1
            for rule in testcase.get("rule_results") or []:
                total_rules += 1
                if not rule.get("passed"):
                    failed_rules += 1

    return {
        "total_functions": total_functions,
        "missing_functions": missing_functions,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "total_rules": total_rules,
        "failed_rules": failed_rules,
    }


def render_rule_test_styles() -> None:
    st.markdown(
        """
<style>
div[class*="st-key-rule_results_header"] {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 18px 20px;
}

.rule-header-title {
  align-items: center;
  color: var(--forest);
  display: flex;
  font-size: 22px;
  font-weight: 850;
  gap: 10px;
  margin: 0;
}

.rule-header-icon {
  align-items: center;
  background: var(--soft-green);
  border-radius: 10px;
  color: var(--emerald);
  display: inline-flex;
  flex-shrink: 0;
  height: 34px;
  justify-content: center;
  width: 34px;
}

.rule-header-icon svg {
  height: 19px;
  width: 19px;
}

.rule-failed-badge {
  background: var(--soft-red);
  border-radius: 999px;
  color: var(--danger);
  display: inline-block;
  font-size: 14px;
  font-weight: 800;
  padding: 7px 16px;
}

.rule-passed-badge {
  background: #DCFCE7;
  border-radius: 999px;
  color: var(--success);
  display: inline-block;
  font-size: 14px;
  font-weight: 800;
  padding: 7px 16px;
}

/* ----- meta row: light label card + dark value panel ----- */
.rule-meta-row {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  margin-top: 16px;
}

.rule-meta-label-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 20px;
}

.rule-meta-label-card .rule-meta-caption {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.rule-meta-label-card .rule-meta-date {
  color: var(--forest);
  font-size: 18px;
  font-weight: 800;
  margin-top: 8px;
}

.rule-meta-value-card {
  background: #0D1B2A;
  border-radius: 16px;
  box-shadow: var(--shadow);
  color: #E5E7EB;
  font-family: Consolas, "SFMono-Regular", Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
  overflow-x: auto;
  padding: 20px;
}

.rule-meta-value-card .rule-kv {
  margin-bottom: 14px;
}

.rule-meta-value-card .rule-k {
  color: #93C5FD;
}

.rule-meta-value-card .rule-v {
  color: #FBBF24;
  word-break: break-all;
}

/* ----- summary row: light stat card + dark mini-stats panel ----- */
.rule-summary-row {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  margin-top: 16px;
}

.rule-stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 20px;
}

.rule-stat-card .rule-stat-number {
  color: var(--forest);
  font-size: 40px;
  font-weight: 900;
  line-height: 1.1;
}

.rule-stat-card .rule-stat-label {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 700;
  margin-top: 4px;
}

.rule-summary-grid {
  background: #0D1B2A;
  border-radius: 16px;
  box-shadow: var(--shadow);
  color: #E5E7EB;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(4, 1fr);
  padding: 20px;
}

.rule-summary-grid .rule-mini-stat {
  text-align: center;
}

.rule-summary-grid .rule-mini-number {
  font-family: Consolas, "SFMono-Regular", Menlo, monospace;
  font-size: 24px;
  font-weight: 800;
}

.rule-summary-grid .rule-mini-number.pass {
  color: #4ADE80;
}

.rule-summary-grid .rule-mini-number.fail {
  color: #F87171;
}

.rule-summary-grid .rule-mini-label {
  color: #94A3B8;
  font-size: 12px;
  font-weight: 700;
  margin-top: 4px;
  text-transform: uppercase;
}

@media (max-width: 760px) {
  .rule-meta-row,
  .rule-summary-row {
    grid-template-columns: 1fr;
  }

  .rule-summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

div[data-testid="stExpander"] {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--soft-shadow);
  margin-top: 14px;
}

div[data-testid="stExpander"] details summary p {
  color: var(--forest);
  font-weight: 850;
}

div[class*="st-key-rule_results_summary"] [data-testid="stMetricValue"] {
  color: var(--forest);
  font-size: 24px;
  font-weight: 900;
}

div[class*="st-key-rule_results_summary"] [data-testid="stMetricLabel"] {
  color: var(--text-secondary);
  font-weight: 800;
}

</style>
        """,
        unsafe_allow_html=True,
    )


def _short_text(value: Any, limit: int = 240) -> str:
    if value in (None, "", [], {}):
        return "-"
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, indent=2, default=str)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _case_failures(testcase: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for rule in testcase.get("rule_results") or []:
        if rule.get("passed"):
            continue
        rule_id = rule.get("rule_id", "Rule")
        rule_type = rule.get("rule_type", "")
        label = f"{rule_id} {rule_type}".strip()
        for failure in rule.get("failures") or ["failed"]:
            failures.append(f"{label}: {failure}")
    return failures


def _case_rows(testcases: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for testcase in testcases:
        case = testcase.get("case") or {}
        execution = testcase.get("execution") or {}
        rules = testcase.get("rule_results") or []
        passed_rules = sum(1 for rule in rules if rule.get("passed"))
        failures = _case_failures(testcase)
        rows.append(
            {
                "Status": "Passed" if testcase.get("passed") else "Failed",
                "Case": str(case.get("name", "-")),
                "Intention": str(case.get("intention", "-")),
                "Input": _short_text(case.get("stdin"), 180),
                "Rules": f"{passed_rules} / {len(rules)}",
                "Failures": "\n".join(failures) if failures else "-",
                "Output": _short_text(execution.get("output"), 420),
            }
        )
    return rows


def _failed_rule_rows(function_name: str, testcases: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for testcase in testcases:
        case = testcase.get("case") or {}
        for rule in testcase.get("rule_results") or []:
            if rule.get("passed"):
                continue
            rows.append(
                {
                    "Function": function_name,
                    "Case": str(case.get("name", "-")),
                    "Rule": f'{rule.get("rule_id", "-")} ({rule.get("rule_type", "-")})',
                    "Expected": _short_text(rule.get("expected"), 260),
                    "Failure": "\n".join(str(item) for item in rule.get("failures") or ["failed"]),
                }
            )
    return rows


def _render_metadata(data: dict[str, Any]) -> None:
    generated_at = escape(str(data.get("generated_at", "-")))
    python_path = escape(str(data.get("python_path", "-")))
    rule_ir_path = escape(str(data.get("rule_ir_path", "-")))

    st.markdown(
        f"""
        <div class="rule-meta-row">
          <div class="rule-meta-label-card">
            <div class="rule-meta-caption">Generated</div>
            <div class="rule-meta-date">{generated_at}</div>
          </div>
          <div class="rule-meta-value-card">
            <div class="rule-kv"><span class="rule-k">Python Path</span><br><span class="rule-v">{python_path}</span></div>
            <div class="rule-kv"><span class="rule-k">Rule IR Path</span><br><span class="rule-v">{rule_ir_path}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_summary(summary: dict[str, int]) -> None:
    pass_fail_class = "fail" if summary["failed_cases"] else "pass"

    st.markdown(
        f"""
        <div class="rule-summary-row">
          <div class="rule-stat-card">
            <div class="rule-stat-number">{summary["total_functions"]}</div>
            <div class="rule-stat-label">Functions</div>
          </div>
          <div class="rule-summary-grid">
            <div class="rule-mini-stat">
              <div class="rule-mini-number pass">{summary["passed_cases"]} / {summary["total_cases"]}</div>
              <div class="rule-mini-label">Cases Passed</div>
            </div>
            <div class="rule-mini-stat">
              <div class="rule-mini-number {pass_fail_class}">{summary["failed_cases"]}</div>
              <div class="rule-mini-label">Cases Failed</div>
            </div>
            <div class="rule-mini-stat">
              <div class="rule-mini-number pass">{summary["total_rules"]}</div>
              <div class="rule-mini-label">Rules Checked</div>
            </div>
            <div class="rule-mini-stat">
              <div class="rule-mini-number {pass_fail_class}">{summary["failed_rules"]}</div>
              <div class="rule-mini-label">Rules Failed</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_function_result(item: dict[str, Any]) -> None:
    testcases = item.get("testcases") or []
    total = len(testcases)
    passed = sum(1 for testcase in testcases if testcase.get("passed"))
    failed = total - passed
    function_name = str(item.get("function", "-"))
    paragraphs = ", ".join(str(value) for value in item.get("paragraphs") or [])
    status = "Found" if item.get("function_found") else "Missing"
    expander_label = f"{function_name} | {passed}/{total} cases passed"

    with st.expander(expander_label, expanded=failed > 0):
        overview_cols = st.columns([0.46, 0.18, 0.18, 0.18])
        overview_cols[0].markdown(f"**Paragraphs:** {paragraphs or '-'}")
        overview_cols[1].metric("Function", status)
        overview_cols[2].metric("Passed", passed)
        overview_cols[3].metric("Failed", failed)

        cases_tab, failed_tab, source_tab = st.tabs(["Cases", "Failed Rules", "Source"])
        with cases_tab:
            rows = _case_rows(testcases)
            st.dataframe(rows, use_container_width=True, hide_index=True, height=min(520, 84 + 42 * max(len(rows), 1)))

        with failed_tab:
            rows = _failed_rule_rows(function_name, testcases)
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True, height=min(480, 84 + 48 * len(rows)))
            else:
                st.success("No failed rules for this function.")

        with source_tab:
            source = item.get("function_source")
            if source:
                st.code(source, language="python", line_numbers=True)
            else:
                st.info("No function source was recorded for this result.")


def render_rule_function_test_report(path: Path = DEFAULT_RESULTS_PATH, title_icon_html: str = "") -> None:
    render_rule_test_styles()
    data = load_rule_function_results(path)
    if data is None:
        st.warning(f"Could not load test results from {path.as_posix()}.")
        return

    summary = summarize_rule_function_results(data)
    with st.container(border=False, key="rule_results_header"):
        left, right = st.columns([0.78, 0.22], vertical_alignment="center")
        with left:
            icon_html = (
                f'<span class="rule-header-icon">{title_icon_html}</span>'
                if title_icon_html
                else ""
            )
            st.markdown(
                f'<h3 class="rule-header-title">{icon_html}Rule Function Test Results</h3>',
                unsafe_allow_html=True,
            )
        with right:
            if summary["failed_cases"]:
                st.markdown(
                    f'<div style="text-align:right;"><span class="rule-failed-badge">{summary["failed_cases"]} Failed</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="text-align:right;"><span class="rule-passed-badge">All Passed</span></div>',
                    unsafe_allow_html=True,
                )

    _render_metadata(data)
    _render_summary(summary)

    for item in data.get("results") or []:
        _render_function_result(item)