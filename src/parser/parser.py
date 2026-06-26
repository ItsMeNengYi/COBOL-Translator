import re


def extract_variables(content):
    variables = []

    variable_pattern = r"^\s*(\d{2})\s+([A-Z0-9-]+)\s+PIC\s+([A-Z0-9()V.-]+)"

    for line in content.splitlines():
        line_upper = line.upper()

        match = re.search(variable_pattern, line_upper)

        if match:
            level = match.group(1)
            name = match.group(2)
            picture = match.group(3)

            variables.append({
                "level": level,
                "name": name,
                "picture": picture
            })

    return variables


def parse_cobol(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    upper_content = content.upper()

    result = {
        "identification": "IDENTIFICATION DIVISION" in upper_content,
        "data": "DATA DIVISION" in upper_content,
        "working_storage": "WORKING-STORAGE SECTION" in upper_content,
        "procedure": "PROCEDURE DIVISION" in upper_content,
        "program_name": None,
        "variables": extract_variables(content)
    }

    program_match = re.search(
        r"PROGRAM-ID\.\s*([A-Z0-9-]+)",
        upper_content
    )

    if program_match:
        result["program_name"] = program_match.group(1)

    return result


if __name__ == "__main__":
    filepath = "data/cobol/ATM.cob"

    result = parse_cobol(filepath)

    print("\n=== COBOL SUMMARY ===")
    print(f"program_name: {result['program_name']}")
    print(f"identification: {result['identification']}")
    print(f"data: {result['data']}")
    print(f"working_storage: {result['working_storage']}")
    print(f"procedure: {result['procedure']}")

    print("\n=== VARIABLES ===")
    for var in result["variables"]:
        print(f"{var['level']} {var['name']} PIC {var['picture']}")