import re
import json


def read_cobol_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def python_safe_name(cobol_name):
    return cobol_name.lower().replace("-", "_")


def parse_repeated_count(token, char):
    """
    Handles:
    X      -> 1
    XX     -> 2
    X(20)  -> 20
    9      -> 1
    99     -> 2
    9(10)  -> 10
    """
    token = token.upper()

    if token == char:
        return 1

    if set(token) == {char}:
        return len(token)

    match = re.fullmatch(rf"{char}\((\d+)\)", token)
    if match:
        return int(match.group(1))

    return None


def parse_pic(pic, usage=None):
    pic = pic.upper().rstrip(".")
    usage = usage.upper() if usage else ""

    result = {
        "pic": pic,
        "cobol_type": "unknown",
        "python_type": "str",
        "length": None,
        "digits": None,
        "scale": 0,
        "usage": usage if usage else None
    }

    # COMP / COMP-3 override rules
    if "COMP-3" in usage:
        result["python_type"] = "Decimal"
    elif "COMP" in usage:
        result["python_type"] = "int"

    # PIC X, XX, X(20)
    x_length = parse_repeated_count(pic, "X")
    if x_length is not None:
        result.update({
            "cobol_type": "alphanumeric",
            "python_type": "str",
            "length": x_length,
            "digits": None,
            "scale": 0
        })
        return result

    # Remove signed prefix for parsing: S9(5), S99
    signed = pic.startswith("S")
    numeric_pic = pic[1:] if signed else pic

    # Decimal PIC: 9(10)V99, 999V99, S9(5)V9(2)
    if "V" in numeric_pic:
        left, right = numeric_pic.split("V", 1)

        left_digits = parse_repeated_count(left, "9")
        right_digits = parse_repeated_count(right, "9")

        if left_digits is not None and right_digits is not None:
            total_digits = left_digits + right_digits

            result.update({
                "cobol_type": "signed_numeric" if signed else "unsigned_numeric",
                "python_type": "Decimal",
                "digits": total_digits,
                "length": total_digits,
                "scale": right_digits
            })
            return result

    # Integer PIC: 9, 99, 999, 9(10), S9(5)
    int_digits = parse_repeated_count(numeric_pic, "9")
    if int_digits is not None:
        result.update({
            "cobol_type": "signed_numeric" if signed else "unsigned_numeric",
            "python_type": "int",
            "digits": int_digits,
            "length": int_digits,
            "scale": 0
        })

        if "COMP-3" in usage:
            result["python_type"] = "Decimal"
        elif "COMP" in usage:
            result["python_type"] = "int"

        return result

    return result


def detect_section(line_index, lines):
    current_section = None

    for i in range(line_index + 1):
        line = lines[i].upper()

        if "FILE SECTION" in line:
            current_section = "FILE SECTION"
        elif "WORKING-STORAGE SECTION" in line:
            current_section = "WORKING-STORAGE"

    return current_section


def extract_initial_value(line):
    match = re.search(r"\bVALUE\s+(.+?)(?:\.|$)", line, re.IGNORECASE)

    if not match:
        return None

    raw_value = match.group(1).strip()

    if raw_value.startswith('"') and raw_value.endswith('"'):
        return raw_value.strip('"')

    upper_value = raw_value.upper()

    if upper_value in ["ZERO", "ZEROES", "ZEROS"]:
        return 0

    if upper_value in ["SPACE", "SPACES"]:
        return "spaces"

    if re.fullmatch(r"-?\d+", raw_value):
        return int(raw_value)

    return raw_value


def extract_usage(line):
    upper = line.upper()

    if "COMP-3" in upper:
        return "COMP-3"

    if "COMP" in upper:
        return "COMP"

    return None


def infer_semantic_role(name):
    upper = name.upper()

    if "BAL" in upper or "BALANCE" in upper:
        return "ACCOUNT_BALANCE"

    if "AMOUNT" in upper or "DEPOSIT" in upper or "WITHDRAW" in upper:
        return "MONEY_AMOUNT"

    if "PIN" in upper:
        return "AUTHENTICATION_PIN"

    if "ACCOUNT" in upper:
        return "ACCOUNT_IDENTIFIER"

    if "NAME" in upper:
        return "CUSTOMER_NAME"

    if "AGE" in upper:
        return "CUSTOMER_AGE"

    if "STATUS" in upper:
        return "FILE_STATUS"

    if "CHOICE" in upper:
        return "MENU_CHOICE"

    return None


def is_money_field(name, pic_info):
    role = infer_semantic_role(name)

    if role in ["ACCOUNT_BALANCE", "MONEY_AMOUNT"]:
        return True

    if pic_info["scale"] and pic_info["scale"] > 0:
        return True

    return False


def build_symbol_table(filepath):
    content = read_cobol_file(filepath)
    lines = content.splitlines()

    symbol_table = {}
    record_stack = []

    variable_pattern = re.compile(
        r"^\s*(\d{2})\s+([A-Z0-9-]+)"
        r"(?:\s+PIC\s+([A-Z0-9()VS.-]+))?"
        r"(?:\s+(COMP-3|COMP))?",
        re.IGNORECASE
    )

    for idx, line in enumerate(lines):
        match = variable_pattern.search(line)

        if not match:
            continue

        level = match.group(1)
        name = match.group(2).upper()
        pic = match.group(3).upper().rstrip(".") if match.group(3) else None
        usage = extract_usage(line)
        section = detect_section(idx, lines)

        if pic is None:
            symbol_table[name] = {
                "level": level,
                "kind": "record",
                "section": section,
                "children": []
            }

            if level == "01":
                record_stack.append(name)

            continue

        pic_info = parse_pic(pic, usage)
        semantic_role = infer_semantic_role(name)

        entry = {
            "level": level,
            "section": section,
            "pic": pic,
            "cobol_type": pic_info["cobol_type"],
            "python_type": pic_info["python_type"],
            "python_name": python_safe_name(name),
            "initial_value": extract_initial_value(line),
            "scale": pic_info["scale"]
        }

        if usage:
            entry["usage"] = usage

        if semantic_role:
            entry["semantic_role"] = semantic_role

        if pic_info["length"] is not None:
            entry["length"] = pic_info["length"]

        if pic_info["digits"] is not None:
            entry["digits"] = pic_info["digits"]

        if pic_info["cobol_type"] == "alphanumeric":
            entry["padding"] = "right-space"

        if is_money_field(name, pic_info):
            entry["python_type"] = "Decimal"
            entry["is_money"] = True
            entry["note"] = "Money-like field or decimal PIC; use Decimal, never float."

        if name == "WS-FILE-STATUS":
            entry["meaning"] = {
                "00": "success",
                "23": "record not found / invalid key",
                "35": "file not found"
            }

        if name == "F-ACCOUNT":
            entry["usage"] = "record_key"

        symbol_table[name] = entry

        if record_stack and level != "01":
            parent = record_stack[-1]
            if parent in symbol_table:
                symbol_table[parent]["children"].append(name)

    return symbol_table


def save_symbol_table(input_path, output_path):
    symbol_table = build_symbol_table(input_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(symbol_table, f, indent=2)

    return symbol_table


if __name__ == "__main__":
    input_path = "data/cobol/ATM.cob"
    output_path = "outputs/symbol_table.json"

    symbol_table = save_symbol_table(input_path, output_path)

    print("Generated outputs/symbol_table.json")
    print(json.dumps(symbol_table, indent=2))