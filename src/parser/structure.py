import re
import json
from pathlib import Path


def read_cobol_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def extract_program_name(content):
    match = re.search(r"PROGRAM-ID\.\s*([A-Z0-9-]+)", content.upper())
    return match.group(1) if match else None


def extract_divisions(content):
    divisions = []
    for div in ["IDENTIFICATION", "ENVIRONMENT", "DATA", "PROCEDURE"]:
        if f"{div} DIVISION" in content.upper():
            divisions.append(div)
    return divisions


def extract_sections(content):
    upper = content.upper()

    sections = {
        "ENVIRONMENT": [],
        "DATA": [],
        "PROCEDURE": []
    }

    if "INPUT-OUTPUT SECTION" in upper:
        sections["ENVIRONMENT"].append("INPUT-OUTPUT")
    if "FILE-CONTROL" in upper:
        sections["ENVIRONMENT"].append("FILE-CONTROL")
    if "FILE SECTION" in upper:
        sections["DATA"].append("FILE SECTION")
    if "WORKING-STORAGE SECTION" in upper:
        sections["DATA"].append("WORKING-STORAGE SECTION")

    return sections


def extract_files(content):
    files = []

    pattern = re.compile(
        r"SELECT\s+([A-Z0-9-]+)\s+ASSIGN\s+TO\s+\"([^\"]+)\""
        r".*?ORGANIZATION\s+IS\s+([A-Z0-9-]+)"
        r".*?ACCESS\s+MODE\s+IS\s+([A-Z0-9-]+)"
        r".*?RECORD\s+KEY\s+IS\s+([A-Z0-9-]+)"
        r".*?FILE\s+STATUS\s+IS\s+([A-Z0-9-]+)",
        re.IGNORECASE | re.DOTALL
    )

    for match in pattern.finditer(content):
        files.append({
            "select_name": match.group(1).upper(),
            "assign_to": match.group(2),
            "organization": match.group(3).upper(),
            "access_mode": match.group(4).upper(),
            "record_key": match.group(5).upper(),
            "file_status": match.group(6).upper()
        })

    return files


def extract_procedure_text(content):
    match = re.search(r"PROCEDURE DIVISION\.(.*)", content, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def extract_paragraphs(content):
    procedure_text = extract_procedure_text(content)
    paragraphs = []

    for line in procedure_text.splitlines():
        stripped = line.strip()

        if re.match(r"^[A-Z0-9-]+\.$", stripped.upper()):
            name = stripped.replace(".", "").upper()

            if name not in ["EXIT", "STOP", "END-IF", "END-PERFORM", "END-EVALUATE"]:
                paragraphs.append(name)

    return paragraphs


def detect_supported_constructs(content):
    upper = content.upper()

    constructs = []

    checks = {
        "OPEN": "OPEN " in upper,
        "CLOSE": "CLOSE " in upper,
        "STOP RUN": "STOP RUN" in upper,
        "IF": "IF " in upper,
        "PERFORM UNTIL": "PERFORM UNTIL" in upper,
        "PERFORM paragraph": "PERFORM " in upper,
        "EVALUATE/WHEN": "EVALUATE " in upper and "WHEN " in upper,
        "MOVE": "MOVE " in upper,
        "DISPLAY": "DISPLAY " in upper,
        "ACCEPT": "ACCEPT " in upper,
        "COMPUTE": "COMPUTE " in upper,
        "READ INVALID KEY": "READ " in upper and "INVALID KEY" in upper,
        "WRITE INVALID KEY": "WRITE " in upper and "INVALID KEY" in upper,
        "REWRITE INVALID KEY": "REWRITE " in upper and "INVALID KEY" in upper,
        "ADD": "ADD " in upper,
        "SUBTRACT": "SUBTRACT " in upper,
        "EXIT": "EXIT." in upper or "EXIT " in upper,
        "EXIT PARAGRAPH": "EXIT PARAGRAPH" in upper
    }

    for name, exists in checks.items():
        if exists:
            constructs.append(name)

    return constructs


def build_program_structure(filepath):
    content = read_cobol_file(filepath)

    return {
        "program_name": extract_program_name(content),
        "source_file": Path(filepath).name,
        "divisions": extract_divisions(content),
        "sections": extract_sections(content),
        "files": extract_files(content),
        "paragraphs": extract_paragraphs(content),
        "supported_constructs_detected": detect_supported_constructs(content)
    }


def save_program_structure(input_path, output_path):
    structure = build_program_structure(input_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2)

    return structure


if __name__ == "__main__":
    input_path = "data/cobol/ATM.cob"
    output_path = "outputs/program_structure.json"

    structure = save_program_structure(input_path, output_path)

    print("Generated outputs/program_structure.json")
    print(json.dumps(structure, indent=2))