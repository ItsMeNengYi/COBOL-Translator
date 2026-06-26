import json


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_summary(output_path, content):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def build_summary():
    structure = read_json("outputs/program_structure.json")
    symbol_table = read_json("outputs/symbol_table.json")
    paragraph_map = read_json("outputs/paragraph_map.json")
    control_flow = read_json("outputs/control_flow.json")
    data_layout = read_json("outputs/data_layout.json")
    rule_ir = read_json("outputs/rule_ir.json")

    program_name = structure["program_name"]
    paragraphs = structure["paragraphs"]
    files = structure["files"]
    rules = rule_ir["rules"]

    business_rules = [
        "Main menu choice must be 1, 2, or 3.",
        "Account name cannot be empty.",
        "User age must be at least 18.",
        "PIN must be a 6-digit number.",
        "Login succeeds only when entered PIN matches the stored PIN.",
        "Deposit amount must be positive.",
        "Deposits increase account balance.",
        "Withdrawal amount must be positive.",
        "Withdrawal is rejected if amount exceeds balance.",
        "Successful withdrawals decrease account balance."
    ]

    money_fields = [
        name for name, meta in symbol_table.items()
        if meta.get("is_money") is True
    ]

    summary = f"""# Program Summary: {program_name}

## Overview

`{program_name}` is a COBOL ATM/account management program. It uses an indexed account file and supports account creation, login, balance inquiry, deposit, withdrawal, and logout.

## Program Structure

- Source file: `{structure.get("source_file")}`
- Language: {structure.get("language")}
- Dialect: {structure.get("dialect")}
- Entry point: `{structure.get("entry_point")}`
- Program type: {structure.get("program_type")}
- Divisions detected: {", ".join(structure.get("divisions", []))}
- Paragraph count: {len(paragraphs)}
- File count: {len(files)}

## Main Paragraphs

"""

    for paragraph, meta in paragraph_map.items():
        summary += f"- `{paragraph}`: {meta.get('purpose')}\n"

    summary += f"""

## File Layout

"""

    for file_name, file_meta in data_layout.get("files", {}).items():
        summary += f"- `{file_name}` assigned to `{file_meta.get('assign_to')}`\n"
        summary += f"  - Organization: {file_meta.get('organization')}\n"
        summary += f"  - Access mode: {file_meta.get('access_mode')}\n"
        summary += f"  - Record key: `{file_meta.get('record_key')}`\n"
        summary += f"  - Record length: {file_meta.get('record_length')}\n"

    summary += f"""

## Important Business Rules

"""

    for rule in business_rules:
        summary += f"- {rule}\n"

    summary += f"""

## Important Data Fields

- Money fields: {", ".join(money_fields)}
- Total variables: {len(symbol_table)}
- Total rules extracted: {len(rules)}
- Control-flow nodes: {len(control_flow.get("nodes", []))}
- Control-flow edges: {len(control_flow.get("edges", []))}
- Loops detected: {len(control_flow.get("loops", []))}

## Notes for Translation and Verification

- Money-like fields must use `Decimal`, never `float`.
- COBOL names with hyphens should be mapped to Python-safe snake_case names.
- Fixed-width string fields such as `F-NAME PIC X(20)` should preserve or intentionally normalize trailing spaces.
- `USERDATA` is an indexed/random-access file keyed by `F-ACCOUNT`.
- `READ`, `WRITE`, and `REWRITE` branches with `INVALID KEY` and `NOT INVALID KEY` must be preserved.
- `DISPLAY` and `ACCEPT` are console I/O and can be abstracted for automated testing.
"""

    return summary


if __name__ == "__main__":
    summary = build_summary()
    write_summary("outputs/program_summary.md", summary)

    print("Generated outputs/program_summary.md")