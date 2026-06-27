from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.report_generator import default_report_data, generate_html_report


APP_NAME = "Avo-cuddle"
REPORT_PATH = Path("reports/migration_report.html")
DEFAULT_COBOL_PATH = Path("inputs/ATM.cob")
LOGO_PATH = Path("assets/avocuddle_logo.svg")
COBOL_DATA_DIR = Path("data/cobol")


def icon_svg(name: str) -> str:
    icons = {
        "logo": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M8 9l-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,
        "settings": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" stroke="currentColor" stroke-width="2"/>
          <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2 2 0 1 1-4 0v-.08A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.08A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2 2 0 1 1 4 0v.08A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.2.6.8 1 1.6 1H21a2 2 0 1 1 0 4h-.08A1.7 1.7 0 0 0 19.4 15z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,
        "copy": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M8 8h10v12H8zM6 16H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
        """,
        "file": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7l-5-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          <path d="M14 2v5h5M9 13h6M9 17h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        """,
        "bolt": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M13 2L4 14h7l-1 8 10-13h-7l0-7z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
        """,
        "test": """
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M9 11l2 2 4-5M8 3h8l1 3h3v15H4V6h3l1-3z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,
    }
    return icons[name]


def logo_data_uri() -> str:
    logo_bytes = LOGO_PATH.read_bytes()
    encoded = base64.b64encode(logo_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def load_default_cobol() -> tuple[str, str, int]:
    if DEFAULT_COBOL_PATH.exists():
        code = DEFAULT_COBOL_PATH.read_text(encoding="utf-8", errors="replace")
        return code, DEFAULT_COBOL_PATH.name, DEFAULT_COBOL_PATH.stat().st_size
    return "", "", 0


def ensure_state() -> None:
    defaults = {
        "cobol_code": "",
        "uploaded_file_name": "",
        "uploaded_file_size": 0,
        "generated_code": "",
        "output_language": "Python",
        "paste_buffer": "",
        "translation_status": "",
        "translation_error": "",
        "show_test_report": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def safe_cobol_filename(filename: str) -> str:
    stem = Path(filename).stem or "uploaded_cobol"
    suffix = Path(filename).suffix.lower() or ".cob"
    if suffix not in {".cob", ".cbl", ".cpy", ".txt"}:
        suffix = ".cob"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "uploaded_cobol"
    return f"{safe_stem}{suffix}"


def write_cobol_input(filename: str, source_code: str) -> Path:
    COBOL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = COBOL_DATA_DIR / safe_cobol_filename(filename)
    target.write_text(source_code, encoding="utf-8")
    return target


def translated_final_path(cobol_path: Path) -> Path:
    return Path("translated") / cobol_path.stem.lower() / "translated_final.py"


def run_pipeline_for_source(filename: str, source_code: str) -> None:
    st.session_state.translation_status = "Running pipeline..."
    st.session_state.translation_error = ""
    st.session_state.generated_code = ""

    cobol_path = write_cobol_input(filename, source_code)
    command = [sys.executable, "-m", "src.pipeline", cobol_path.as_posix()]
    try:
        subprocess.run(command, cwd=Path.cwd(), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        st.session_state.translation_status = "Pipeline failed"
        st.session_state.translation_error = (exc.stderr or exc.stdout or str(exc)).strip()
        return

    final_path = translated_final_path(cobol_path)
    if final_path.exists():
        st.session_state.generated_code = final_path.read_text(encoding="utf-8", errors="replace")
        st.session_state.translation_status = f"Loaded {final_path.as_posix()}"
    else:
        st.session_state.translation_status = "Pipeline completed, but translated_final.py was not found"
        st.session_state.translation_error = f"Expected output: {final_path.as_posix()}"


def render_copy_button(text: str) -> None:
    payload = json.dumps(text)
    components.html(
        f"""
        <style>
          html, body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: "Source Sans Pro", sans-serif;
          }}
          #copy-code {{
            align-items: center;
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            color: #083C2F;
            cursor: pointer;
            display: inline-flex;
            font-size: 1rem;
            font-weight: 600;
            gap: 8px;
            justify-content: center;
            line-height: 1.2;
            min-height: 40px;
            padding: 0 16px;
            width: 100%;
          }}
          #copy-code:hover {{
            background: #F8FAF9;
          }}
          #copy-code svg {{
            height: 18px;
            width: 18px;
          }}
        </style>
        <button id="copy-code" style="
          width: 100%;
        ">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M8 8h10v12H8zM6 16H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          </svg>
          <span>Copy Code</span>
        </button>
        <script>
          const btn = document.getElementById("copy-code");
          const label = btn.querySelector("span");
          const codeText = {payload};

          async function copyToClipboard(value) {{
            try {{
              await navigator.clipboard.writeText(value);
              return true;
            }} catch (err) {{
              // Fallback for browsers/environments where Clipboard API is restricted.
              const area = document.createElement("textarea");
              area.value = value;
              area.setAttribute("readonly", "");
              area.style.position = "fixed";
              area.style.top = "-9999px";
              document.body.appendChild(area);
              area.select();
              const ok = document.execCommand("copy");
              document.body.removeChild(area);
              return ok;
            }}
          }}

          function flashMessage(message) {{
            const original = label.textContent;
            label.textContent = message;
            setTimeout(() => label.textContent = original, 1200);
          }}

          btn.addEventListener("click", async () => {{
            if (!codeText || !codeText.trim()) {{
              flashMessage("No code yet");
              return;
            }}

            const copied = await copyToClipboard(codeText);
            flashMessage(copied ? "Copied" : "Copy failed");
          }});
        </script>
        """,
        height=46,
    )


def translate_cobol_to_python(cobol_code: str) -> str:
    # Future integration point: translator.py
    if not cobol_code.strip():
        return ""
    return '''from decimal import Decimal


class ATMAccount:
    def __init__(self, balance=Decimal("0.00")):
        self.balance = Decimal(str(balance))

    def deposit(self, amount):
        amount = Decimal(str(amount))
        self.balance += amount
        return f"Deposited: {amount:.2f}"

    def withdraw(self, amount):
        amount = Decimal(str(amount))
        if amount > self.balance:
            return "Insufficient balance.\\nTransaction cancelled."

        self.balance -= amount
        return f"Withdraw: {amount:.2f}\\nNew Balance: {self.balance:.2f}"

    def balance_inquiry(self):
        return f"Balance: {self.balance:.2f}"


def main():
    account = ATMAccount("150.00")
    print("WELCOME TO ATM SYSTEM")
    print("1. DEPOSIT")
    print("2. WITHDRAW")
    print("3. BALANCE")


if __name__ == "__main__":
    main()
'''


def run_translation() -> None:
    filename = st.session_state.uploaded_file_name or "pasted-source.cob"
    run_pipeline_for_source(filename, st.session_state.cobol_code)


def test_report_rows() -> list[dict[str, str]]:
    # Future integration point: test_runner.py
    return [
        {
            "Status": "TC-01",
            "Scenario": "Deposit valid amount",
            "Description": "Deposit a valid amount",
            "Expected Output": "Deposited: 100.00",
            "Actual Output": "Deposited: 100.00",
            "Result": "Passed",
        },
        {
            "Status": "TC-02",
            "Scenario": "Balance inquiry",
            "Description": "Read account balance after setup",
            "Expected Output": "Balance: 150.00",
            "Actual Output": "Balance: 150.00",
            "Result": "Passed",
        },
        {
            "Status": "TC-03",
            "Scenario": "Withdraw valid amount",
            "Description": "Withdraw amount below available balance",
            "Expected Output": "Withdraw: 50.00\nNew Balance: 100.00",
            "Actual Output": "Withdraw: 50.00\nNew Balance: 100.00",
            "Result": "Passed",
        },
        {
            "Status": "TC-04",
            "Scenario": "Withdraw over balance",
            "Description": "Withdraw amount greater than balance",
            "Expected Output": "Insufficient balance.\nTransaction cancelled.",
            "Actual Output": "Withdraw: 500.00\nNew Balance: -350.00",
            "Result": "Failed",
        },
    ]


def render_test_report_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        failed = row["Result"] == "Failed"
        output_class = " output-failed" if failed else ""
        body.append(
            f"""
            <tr class="{'failed-row' if failed else ''}">
              <td><span class="status-mark {'mark-fail' if failed else 'mark-pass'}"></span><span class="status-pill {'fail-pill' if failed else 'pass-pill'}">{escape(row["Status"])}</span></td>
              <td>{escape(row["Scenario"])}</td>
              <td>{escape(row["Description"])}</td>
              <td><pre class="output-cell{output_class}">{escape(row["Expected Output"])}</pre></td>
              <td><pre class="output-cell{output_class}">{escape(row["Actual Output"])}</pre></td>
            </tr>
            """
        )
    return f"""
    <div class="report-table-wrap">
      <table class="report-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Scenario</th>
            <th>Description</th>
            <th>Expected Output</th>
            <th>Actual Output</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </div>
    """


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --bg: #F8FAF9;
          --card: #FFFFFF;
          --primary: #6FB62C;
          --primary-dark: #5DA425;
          --secondary: #93C83E;
          --forest: #083C2F;
          --emerald: #0F5D46;
          --seed: #6B3F1A;
          --text: #0F172A;
          --text-secondary: #64748B;
          --border: #E5E7EB;
          --success: #16A34A;
          --warning: #F59E0B;
          --danger: #DC2626;
          --info: #2563EB;
          --soft-green: #EAF7E8;
          --soft-red: #FEE2E2;
          --soft-yellow: #FEF3C7;
          --soft-blue: #EFF6FF;
          --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
          --soft-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }

        .stApp {
          background: var(--bg);
          color: var(--text);
        }

        [data-testid="stHeader"] {
          background: transparent;
        }

        .block-container {
          max-width: 1420px;
          padding: 28px 32px 44px;
        }

        h1, h2, h3, p {
          letter-spacing: 0;
        }

        .brand {
          align-items: center;
          display: flex;
          gap: 18px;
        }

        .logo {
          align-items: center;
          background: transparent;
          border-radius: 0;
          display: inline-flex;
          height: 60px;
          justify-content: center;
          width: auto;
        }

        .logo img {
          display: block;
          height: 60px;
          max-width: 230px;
          object-fit: contain;
          width: auto;
        }

        .brand-title {
          color: var(--text);
          font-size: 28px;
          font-weight: 800;
          line-height: 1.1;
        }

        .brand-subtitle {
          color: var(--text-secondary);
          font-size: 15px;
          margin-top: 4px;
        }

        div[class*="st-key-header_report"] button,
        div[class*="st-key-bottom_report"] button {
          background: white;
          border: 1px solid var(--border);
          border-radius: 12px;
          box-shadow: var(--soft-shadow);
          color: var(--forest);
          font-weight: 750;
          min-height: 44px;
          padding: 0 18px;
        }

        div[class*="st-key-header_report"] button:hover,
        div[class*="st-key-bottom_report"] button:hover {
          background: #F8FAF9;
          border: 1px solid var(--border);
          color: var(--forest);
        }

        .panel-card,
        .action-card,
        .report-card,
        .st-key-source_card,
        .st-key-generated_card,
        .st-key-bottom_report_card {
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: 16px;
          box-shadow: var(--shadow);
        }

        .st-key-source_card,
        .st-key-generated_card {
          display: flex;
          flex-direction: column;
          min-height: 680px;
          overflow: hidden;
          padding: 20px;
        }

        .panel-title {
          align-items: center;
          color: var(--forest);
          display: flex;
          font-size: 17px;
          font-weight: 800;
          gap: 10px;
          margin-bottom: 16px;
        }

        .title-icon {
          align-items: center;
          background: var(--soft-green);
          border-radius: 10px;
          color: var(--emerald);
          display: inline-flex;
          height: 34px;
          justify-content: center;
          width: 34px;
        }

        .title-icon svg,
        .file-pill svg {
          height: 19px;
          width: 19px;
        }

        .info-row {
          align-items: center;
          background: var(--soft-green);
          border: 1px solid var(--border);
          border-radius: 12px;
          color: var(--text);
          display: flex;
          flex-wrap: wrap;
          font-size: 14px;
          gap: 8px;
          justify-content: space-between;
          margin: 0 0 14px;
          padding: 12px 14px;
        }

        .file-pill-row {
          align-items: center;
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .file-pill {
          align-items: center;
          background: #ffffff;
          border: 1px solid var(--border);
          border-radius: 10px;
          display: inline-flex;
          font-size: 13px;
          font-weight: 750;
          gap: 8px;
          min-height: 36px;
          padding: 7px 10px;
        }

        .file-pill svg {
          color: var(--emerald);
        }

        .status-badge {
          background: #DCFCE7;
          border-radius: 999px;
          color: var(--success);
          font-size: 12px;
          font-weight: 800;
          padding: 4px 10px;
        }

        .upload-label {
          color: var(--text);
          font-size: 14px;
          font-weight: 750;
          margin-bottom: 8px;
        }

        .support-text,
        .language-label,
        .action-subtitle {
          color: var(--text-secondary);
        }

        .empty-note {
          background: #F3F4F6;
          border: 1px solid var(--border);
          border-radius: 12px;
          color: #475569;
          font-size: 14px;
          padding: 12px 14px;
        }

        .language-label {
          font-size: 12px;
          font-weight: 800;
          margin-bottom: 4px;
          text-transform: uppercase;
        }

        div[data-testid="stFileUploader"] section {
          align-items: center;
          background: #F8FAF9;
          border: 1px dashed #CBD5E1;
          border-radius: 16px;
          min-height: 220px;
          padding: 28px;
        }

        div[data-testid="stFileUploader"] section:hover {
          background: #F3F4F6;
          border-color: #94A3B8;
        }

        div[data-testid="stDownloadButton"] button,
        div[class*="st-key-copy_code"] button,
        div[class*="st-key-clear_source"] button {
          background: white;
          border: 1px solid var(--border);
          border-radius: 12px;
          color: var(--forest);
          font-weight: 700;
          min-height: 40px;
        }

        div[data-testid="stDownloadButton"] button {
          background: white;
          border: 1px solid var(--border);
          color: var(--forest);
        }

        div[data-testid="stDownloadButton"] button:hover {
          background: #F8FAF9;
          border: 1px solid var(--border);
          color: var(--forest);
        }

        .st-key-bottom_report_card {
          min-height: 108px;
          padding: 20px;
        }

        div[class*="st-key-test_toggle"] button {
          background: #F3F4F6;
          border: 1px solid var(--border);
          border-radius: 16px;
          color: #475569;
          font-size: 18px;
          font-weight: 850;
          min-height: 108px;
          width: 100%;
        }

        div[class*="st-key-test_toggle"] button:hover {
          background: #E5E7EB;
          border-color: #CBD5E1;
          color: #334155;
        }

        .report-card {
          margin-top: 24px;
          padding: 22px;
        }

        .report-head {
          align-items: center;
          display: flex;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .report-title {
          align-items: center;
          color: var(--forest);
          display: flex;
          font-size: 20px;
          font-weight: 850;
          gap: 10px;
        }

        .failed-badge {
          background: var(--soft-red);
          border-radius: 999px;
          color: var(--danger);
          font-size: 13px;
          font-weight: 850;
          padding: 6px 12px;
        }

        .report-table-wrap {
          overflow-x: auto;
        }

        .report-table {
          border-collapse: collapse;
          width: 100%;
        }

        .report-table th {
          background: #f8fafc;
          color: #475569;
          font-size: 12px;
          font-weight: 850;
          padding: 12px;
          text-align: left;
        }

        .report-table td {
          border-top: 1px solid var(--border);
          color: var(--text);
          font-size: 14px;
          padding: 12px;
          vertical-align: top;
        }

        .status-pill {
          border-radius: 999px;
          display: inline-flex;
          font-weight: 850;
          padding: 5px 10px;
          white-space: nowrap;
        }

        .status-mark {
          border-radius: 999px;
          display: inline-flex;
          height: 14px;
          margin-right: 10px;
          vertical-align: middle;
          width: 14px;
        }

        .mark-pass {
          background: var(--success);
        }

        .mark-fail {
          background: var(--danger);
        }

        .pass-pill {
          background: #DCFCE7;
          color: var(--success);
        }

        .fail-pill {
          background: var(--soft-red);
          color: var(--danger);
        }

        .output-cell {
          background: #f8fafc;
          border-radius: 10px;
          color: #334155;
          font-family: Consolas, "SFMono-Regular", Menlo, monospace;
          font-size: 12px;
          margin: 0;
          padding: 10px;
          white-space: pre-wrap;
        }

        .output-failed {
          background: #fff1f2;
          color: var(--danger);
        }

        code .k,
        code .kn,
        code .kd,
        code .nb {
          color: var(--info) !important;
        }

        code .s,
        code .s1,
        code .s2 {
          color: var(--success) !important;
        }

        code .m,
        code .mi,
        code .mf {
          color: var(--seed) !important;
        }

        code .c,
        code .c1 {
          color: var(--text-secondary) !important;
        }

        @media (max-width: 1000px) {
          .bottom-actions {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 760px) {
          .block-container {
            padding: 22px 16px 36px;
          }

          .brand-title {
            font-size: 24px;
          }

          .logo,
          .logo img {
            height: 44px;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
def generate_report_silently() -> None:
    # Future integration point: report_generator.py data assembled from parser/extractor/test runner.
    generate_html_report(default_report_data(), REPORT_PATH)


def render_header() -> None:
    left, right = st.columns([0.72, 0.28], vertical_alignment="center")
    with left:
        st.markdown(
            f"""
            <div class="brand">
              <div class="logo"><img src="{logo_data_uri()}" alt="AvoCuddle COBOL Migrator logo"></div>
              <div>
                <div class="brand-title">Avo-cuddle</div>
                <div class="brand-subtitle">COBOL to Modern Code Converter</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        pass


def render_source_panel() -> None:
    with st.container(border=False, key="source_card"):
        head_col, clear_col = st.columns([0.8, 0.2], vertical_alignment="center")
        with head_col:
            st.markdown(
                f'<div class="panel-title"><span class="title-icon">{icon_svg("file")}</span>COBOL Source Code</div>',
                unsafe_allow_html=True,
            )
        with clear_col:
            if st.session_state.cobol_code and st.button("Clear", key="clear_source", icon=":material/delete:", use_container_width=True):
                st.session_state.cobol_code = ""
                st.session_state.generated_code = ""
                st.session_state.uploaded_file_name = ""
                st.session_state.uploaded_file_size = 0
                st.session_state.paste_buffer = ""
                st.session_state.translation_status = ""
                st.session_state.translation_error = ""
                st.rerun()

        if st.session_state.cobol_code:
            filename = st.session_state.uploaded_file_name or "source.cob"
            file_size = format_size(st.session_state.uploaded_file_size)
            st.markdown(
                f"""
                <div class="info-row">
                  <div class="file-pill-row">
                    <span class="file-pill">{icon_svg("file")}{escape(filename)}</span>
                    <span class="file-pill">{escape(file_size)}</span>
                    <span class="status-badge">Uploaded</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.code(st.session_state.cobol_code, language="text", line_numbers=True)
        else:
            st.markdown('<div class="upload-label">Drag & drop COBOL file here or click to browse</div>', unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "COBOL upload",
                type=["cob", "cbl", "cpy", "txt"],
                label_visibility="collapsed",
            )
            if uploaded_file is not None:
                raw = uploaded_file.getvalue()
                st.session_state.cobol_code = raw.decode("utf-8", errors="replace")
                st.session_state.uploaded_file_name = uploaded_file.name
                st.session_state.uploaded_file_size = len(raw)
                with st.spinner("Running COBOL migration pipeline..."):
                    run_translation()
                st.rerun()

            st.markdown('<div class="support-text">Supported formats: .cob, .cbl, .cpy, .txt</div>', unsafe_allow_html=True)
            st.markdown('<div class="upload-label" style="margin-top:18px;">Or paste COBOL source code</div>', unsafe_allow_html=True)
            pasted_code = st.text_area(
                "Paste COBOL source code",
                key="paste_buffer",
                height=180,
                placeholder="Paste COBOL code here...",
                label_visibility="collapsed",
            )
            if pasted_code.strip():
                st.session_state.cobol_code = pasted_code
                st.session_state.uploaded_file_name = "pasted-source.cob"
                st.session_state.uploaded_file_size = len(pasted_code.encode("utf-8"))
                with st.spinner("Running COBOL migration pipeline..."):
                    run_translation()
                st.rerun()


def render_generated_panel() -> None:
    if st.session_state.cobol_code and not st.session_state.generated_code:
        run_translation()

    with st.container(border=False, key="generated_card"):
        title_col, lang_col = st.columns([0.62, 0.38], vertical_alignment="center")
        with title_col:
            st.markdown(
                f'<div class="panel-title"><span class="title-icon">{icon_svg("bolt")}</span>Generated Code</div>',
                unsafe_allow_html=True,
            )
        with lang_col:
            st.markdown('<div class="language-label">Output Language</div>', unsafe_allow_html=True)
            st.selectbox(
                "Output Language",
                ["Python"],
                index=0,
                key="output_language",
                label_visibility="collapsed",
                help="Architecture is ready for JavaScript, Java, and C# translator modules.",
            )

        copy_col, download_col = st.columns(2)
        with copy_col:
            render_copy_button(st.session_state.generated_code or "")
        with download_col:
            st.download_button(
                "Download .py",
                data=st.session_state.generated_code or "",
                file_name="translated_code.py",
                mime="text/x-python",
                icon=":material/download:",
                use_container_width=True,
            )

        if st.session_state.generated_code:
            st.code(st.session_state.generated_code, language="python", line_numbers=True)
        else:
            if st.session_state.translation_error:
                st.error(st.session_state.translation_error)
            st.markdown(
                '<div class="empty-note">Generated Python code will appear automatically after upload.</div>',
                unsafe_allow_html=True,
            )


def render_bottom_actions() -> None:
    passed = 10
    total = 11
    failed = total - passed

    left, right = st.columns(2, gap="large")
    with left:
        if st.button(
            f"{passed} / {total} Passed\nClick to view details",
            key="test_toggle",
            icon=":material/error:",
            use_container_width=True,
        ):
            st.session_state.show_test_report = not st.session_state.show_test_report
    with right:
        with st.container(border=False, key="bottom_report_card"):
            if st.button("Generate Report", key="bottom_report", icon=":material/description:", use_container_width=True):
                generate_report_silently()
            st.markdown('<div class="action-subtitle">Download HTML report</div>', unsafe_allow_html=True)


def render_test_report() -> None:
    rows = test_report_rows()
    failed_count = sum(1 for row in rows if row["Result"] == "Failed")
    st.markdown(
        f"""
        <section class="report-card">
          <div class="report-head">
            <div class="report-title"><span class="title-icon">{icon_svg("test")}</span>Test Case Report</div>
            <span class="failed-badge">{failed_count} Failed</span>
          </div>
          {render_test_report_table(rows)}
        </section>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon=":material/code:", layout="wide")
    ensure_state()
    inject_styles()

    render_header()
    left, right = st.columns(2, gap="large")
    with left:
        render_source_panel()
    with right:
        render_generated_panel()

    render_bottom_actions()
    if st.session_state.show_test_report:
        render_test_report()


if __name__ == "__main__":
    main()
