import re
import json


def read_cobol_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def extract_procedure_lines(content):
    lines = content.splitlines()

    start_idx = None
    end_idx = len(lines)

    for i, line in enumerate(lines):
        if "PROCEDURE DIVISION" in line.upper():
            start_idx = i + 1
        if "END PROGRAM" in line.upper():
            end_idx = i
            break

    if start_idx is None:
        return []

    return list(enumerate(lines[start_idx:end_idx], start=start_idx + 1))


def is_paragraph_header(line):
    stripped = line.strip().upper()

    if re.match(r"^[A-Z0-9-]+\.$", stripped):
        name = stripped.replace(".", "")
        ignore = {
            "EXIT",
            "STOP",
            "END-IF",
            "END-PERFORM",
            "END-EVALUATE"
        }
        return name not in ignore

    return False


def get_paragraph_name(line):
    return line.strip().replace(".", "").upper()


def extract_perform_calls(lines):
    calls = []

    for _, line in lines:
        upper = line.upper()

        # Ignore PERFORM UNTIL because it is a loop, not a paragraph call
        if "PERFORM UNTIL" in upper:
            continue

        matches = re.findall(r"\bPERFORM\s+([A-Z0-9-]+)", upper)

        for match in matches:
            if match not in ["UNTIL", "VARYING"]:
                calls.append(match)

    return sorted(list(set(calls)))


def infer_purpose(paragraph_name):
    purposes = {
        "MAIN-PROCEDURE": "Open account file, handle main menu, route to account creation or login, then close file.",
        "CREATE-ACCOUNT": "Collect name, age, PIN; validate inputs; generate account number; create account record.",
        "GENERATE-ACCOUNT": "Generate random account number and retry if it already exists.",
        "LOGIN": "Read account, validate existence and PIN, then enter ATM menu until logout.",
        "ATM-MENU": "Show post-login menu and route to balance, deposit, withdraw, or logout.",
        "CHECK-BALANCE": "Display current account balance.",
        "DEPOSIT": "Accept positive deposit amount, add it to balance, and update account record.",
        "WITHDRAW": "Accept positive withdrawal amount, check sufficient balance, subtract it, and update account record if valid."
    }

    return purposes.get(paragraph_name, "Purpose not inferred.")


def build_paragraph_map(filepath):
    content = read_cobol_file(filepath)
    procedure_lines = extract_procedure_lines(content)

    paragraph_headers = []

    for line_no, line in procedure_lines:
        if is_paragraph_header(line):
            paragraph_headers.append({
                "name": get_paragraph_name(line),
                "line_no": line_no
            })

    paragraph_map = {}

    for i, paragraph in enumerate(paragraph_headers):
        name = paragraph["name"]
        start_line = paragraph["line_no"]

        if i + 1 < len(paragraph_headers):
            end_line = paragraph_headers[i + 1]["line_no"] - 1
        else:
            end_line = procedure_lines[-1][0] if procedure_lines else start_line

        paragraph_body = [
            item for item in procedure_lines
            if start_line <= item[0] <= end_line
        ]

        paragraph_map[name] = {
            "start_line": start_line,
            "end_line": end_line,
            "calls": extract_perform_calls(paragraph_body),
            "purpose": infer_purpose(name)
        }

    return paragraph_map


def save_paragraph_map(input_path, output_path):
    paragraph_map = build_paragraph_map(input_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(paragraph_map, f, indent=2)

    return paragraph_map


if __name__ == "__main__":
    input_path = "data/cobol/ATM.cob"
    output_path = "outputs/paragraph_map.json"

    paragraph_map = save_paragraph_map(input_path, output_path)

    print("Generated outputs/paragraph_map.json")
    print(json.dumps(paragraph_map, indent=2))