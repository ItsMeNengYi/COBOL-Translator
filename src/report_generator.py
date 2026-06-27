from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


def _rows(items: list[dict[str, Any]], columns: list[str]) -> str:
    if not items:
        return (
            f"<tr><td colspan=\"{len(columns)}\" class=\"empty\">"
            "No data available yet.</td></tr>"
        )

    rendered_rows = []
    for item in items:
        cells = "".join(f"<td>{escape(str(item.get(column, '')))}</td>" for column in columns)
        rendered_rows.append(f"<tr>{cells}</tr>")
    return "\n".join(rendered_rows)


def _table(title: str, items: list[dict[str, Any]], columns: list[str]) -> str:
    headings = "".join(f"<th>{escape(column)}</th>" for column in columns)
    return f"""
    <section class="card">
      <h2>{escape(title)}</h2>
      <div class="table-wrap">
        <table>
          <thead><tr>{headings}</tr></thead>
          <tbody>{_rows(items, columns)}</tbody>
        </table>
      </div>
    </section>
    """


def default_report_data() -> dict[str, Any]:
    """Sample report data used until real analysis modules are connected."""
    return {
        "summary": {
            "test_cases_run": 12,
            "passed": 11,
            "failed": 1,
            "pass_rate": "91.7%",
        },
        "business_rules": [
            {
                "Rule ID": "BR-001",
                "Paragraph": "VALIDATE-ACCOUNT",
                "Type": "Validation",
                "Target": "Account Number",
                "Business Category": "Customer Account",
                "Risk": "Low",
                "Description": "Rejects requests when the account identifier is missing or malformed.",
            },
            {
                "Rule ID": "BR-002",
                "Paragraph": "CHECK-BALANCE",
                "Type": "Decision",
                "Target": "Withdrawal Amount",
                "Business Category": "Funds Availability",
                "Risk": "Medium",
                "Description": "Compares requested cash amount against current ledger balance.",
            },
            {
                "Rule ID": "BR-003",
                "Paragraph": "APPLY-FEE",
                "Type": "Calculation",
                "Target": "Transaction Fee",
                "Business Category": "Fee Processing",
                "Risk": "Medium",
                "Description": "Applies fee logic for out-of-network withdrawal transactions.",
            },
        ],
        "test_results": [
            {
                "Test Case ID": "TC-001",
                "Description": "Valid balance inquiry",
                "Expected": "Balance returned",
                "Actual": "Balance returned",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-002",
                "Description": "Withdrawal below balance",
                "Expected": "Approved",
                "Actual": "Approved",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-003",
                "Description": "Withdrawal equal to balance",
                "Expected": "Approved with zero balance",
                "Actual": "Approved with zero balance",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-004",
                "Description": "Withdrawal above balance",
                "Expected": "Rejected",
                "Actual": "Rejected",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-005",
                "Description": "Invalid account number",
                "Expected": "Validation error",
                "Actual": "Validation error",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-006",
                "Description": "Daily withdrawal limit exceeded",
                "Expected": "Rejected",
                "Actual": "Rejected",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-007",
                "Description": "Fee applied to network transaction",
                "Expected": "No fee",
                "Actual": "No fee",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-008",
                "Description": "Fee applied to external transaction",
                "Expected": "Fee deducted",
                "Actual": "Fee deducted",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-009",
                "Description": "PIN retry count reached",
                "Expected": "Card locked",
                "Actual": "Card locked",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-010",
                "Description": "Decimal amount rounding",
                "Expected": "Banker's rounding",
                "Actual": "Standard rounding",
                "Status": "Failed",
            },
            {
                "Test Case ID": "TC-011",
                "Description": "Successful receipt print",
                "Expected": "Receipt generated",
                "Actual": "Receipt generated",
                "Status": "Passed",
            },
            {
                "Test Case ID": "TC-012",
                "Description": "Timeout cancellation",
                "Expected": "Transaction cancelled",
                "Actual": "Transaction cancelled",
                "Status": "Passed",
            },
        ],
        "mismatches": [
            {
                "Mismatch ID": "MM-001",
                "Description": "Decimal rounding differs for half-cent values.",
                "Severity": "Medium",
                "COBOL": "ROUNDED numeric assignment",
                "Python/JavaScript": "Default round behavior",
                "Suggestion": "Add an explicit Decimal rounding mode matching COBOL compiler settings.",
            },
            {
                "Mismatch ID": "MM-002",
                "Description": "Whitespace padding behavior needs confirmation for fixed-width fields.",
                "Severity": "Low",
                "COBOL": "PIC X field padding",
                "Python/JavaScript": "Variable-length string",
                "Suggestion": "Apply fixed-width formatting at system boundaries.",
            },
        ],
    }


def generate_html_report(
    report_data: dict[str, Any] | None = None,
    output_path: str | Path = "reports/migration_report.html",
) -> Path:
    data = report_data or default_report_data()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    summary = data["summary"]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>COBOL Migration Report</title>
  <style>
    :root {{
      --navy: #0b1f33;
      --teal: #0f9f9a;
      --blue: #2563eb;
      --green: #16a34a;
      --red: #dc2626;
      --orange: #f59e0b;
      --ink: #14213d;
      --muted: #64748b;
      --line: #e2e8f0;
      --bg: #f6f9fc;
      --card: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, Segoe UI, Arial, sans-serif;
    }}
    header {{
      background: linear-gradient(135deg, var(--navy), #103b4f 70%, var(--teal));
      color: white;
      padding: 34px 44px;
    }}
    header p {{ margin: 8px 0 0; color: #c8f5f2; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }}
    .metric, .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 14px 34px rgba(15, 31, 51, 0.08);
    }}
    .metric {{ padding: 20px; }}
    .metric span {{ color: var(--muted); font-size: 13px; font-weight: 700; text-transform: uppercase; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 30px; }}
    .card {{ margin: 18px 0; padding: 22px; }}
    h1, h2 {{ margin: 0; }}
    h2 {{ margin-bottom: 16px; font-size: 20px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #f1f8fb; color: #17445c; font-size: 12px; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ color: var(--muted); text-align: center; }}
    @media (max-width: 760px) {{ .cards {{ grid-template-columns: 1fr; }} main {{ padding: 18px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>COBOL Modernization Migration Report</h1>
    <p>Generated {escape(generated_at)}</p>
  </header>
  <main>
    <section class="cards">
      <div class="metric"><span>Test Cases Run</span><strong>{escape(str(summary["test_cases_run"]))}</strong></div>
      <div class="metric"><span>Passed / Failed</span><strong>{escape(str(summary["passed"]))} / {escape(str(summary["failed"]))}</strong></div>
      <div class="metric"><span>Pass Rate</span><strong>{escape(str(summary["pass_rate"]))}</strong></div>
    </section>
    {_table("Extracted Business Rules", data["business_rules"], ["Rule ID", "Paragraph", "Type", "Target", "Business Category", "Risk", "Description"])}
    {_table("Test Case Details", data["test_results"], ["Test Case ID", "Description", "Expected", "Actual", "Status"])}
    {_table("Mismatch Analysis", data["mismatches"], ["Mismatch ID", "Description", "Severity", "COBOL", "Python/JavaScript", "Suggestion"])}
  </main>
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(generate_html_report())
