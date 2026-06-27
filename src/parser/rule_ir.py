import re
import json


def read_cobol_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def read_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_paragraph_body(content, start_line, end_line):
    lines = content.splitlines()
    return lines[start_line - 1:end_line]


def clean_line(line):
    return line.strip().rstrip(".").strip()


def normalize_operator(condition):
    condition = condition.upper()
    replacements = {
        " IS EQUAL TO ": " = ",
        " IS GREATER THAN ": " > ",
        " IS LESS THAN ": " < ",
        " IS NOT EQUAL TO ": " != ",
        " GREATER THAN OR EQUAL TO ": " >= ",
        " LESS THAN OR EQUAL TO ": " <= ",
        " GREATER THAN ": " > ",
        " LESS THAN ": " < ",
        " OR ": " OR ",
        " AND ": " AND "
    }

    for old, new in replacements.items():
        condition = condition.replace(old, new)

    return condition.strip()


def parse_condition(condition_text):
    condition_text = normalize_operator(condition_text).strip().rstrip(".")

    # Handle simple OR/AND raw condition first
    if " OR " in condition_text or " AND " in condition_text:
        return {"raw": condition_text}

    operators = [">=", "<=", "!=", "=", ">", "<"]

    for op in operators:
        if op in condition_text:
            left, right = condition_text.split(op, 1)
            return {
                "left": left.strip(),
                "operator": "==" if op == "=" else op,
                "right": right.strip().strip('"')
            }

    return {"raw": condition_text}


def parse_display(line):
    """
    Handles:
    DISPLAY "HELLO"
    DISPLAY F-BAL
    DISPLAY "WELCOME, " F-NAME
    """
    content = clean_line(line)
    content = re.sub(r"^DISPLAY\s+", "", content, flags=re.IGNORECASE).strip()

    quoted_parts = re.findall(r'"([^"]*)"', content)
    remaining = re.sub(r'"[^"]*"', "", content).strip()

    variables = [
        token for token in remaining.split()
        if re.match(r"^[A-Z0-9-]+$", token.upper())
    ]

    if quoted_parts and variables:
        return {
            "operation": "DISPLAY",
            "parts": quoted_parts + [v.upper() for v in variables]
        }

    if quoted_parts:
        return {
            "operation": "DISPLAY",
            "value": " ".join(quoted_parts)
        }

    return {
        "operation": "DISPLAY",
        "source": content.upper()
    }


def parse_operation_line(line):
    upper = clean_line(line).upper()

    if not upper:
        return None

    move_match = re.match(r'MOVE\s+(.+?)\s+TO\s+([A-Z0-9-]+)', upper)
    if move_match:
        return {
            "operation": "MOVE",
            "source": move_match.group(1).strip().strip('"'),
            "target": move_match.group(2).strip()
        }

    add_match = re.match(r'ADD\s+([A-Z0-9-]+)\s+TO\s+([A-Z0-9-]+)', upper)
    if add_match:
        return {
            "operation": "ADD",
            "source": add_match.group(1),
            "target": add_match.group(2)
        }

    subtract_match = re.match(r'SUBTRACT\s+([A-Z0-9-]+)\s+FROM\s+([A-Z0-9-]+)', upper)
    if subtract_match:
        return {
            "operation": "SUBTRACT",
            "source": subtract_match.group(1),
            "target": subtract_match.group(2)
        }

    compute_match = re.match(r'COMPUTE\s+([A-Z0-9-]+)\s*=\s*(.+)', upper)
    if compute_match:
        return {
            "operation": "COMPUTE",
            "target": compute_match.group(1),
            "expression": compute_match.group(2).strip()
        }

    perform_until_match = re.match(
        r'PERFORM\s+([A-Z0-9-]+)\s+UNTIL\s+(.+)',
        upper
    )
    if perform_until_match:
        return {
            "operation": "PERFORM_UNTIL",
            "target": perform_until_match.group(1),
            "condition": parse_condition(perform_until_match.group(2))
        }

    perform_match = re.match(r'PERFORM\s+([A-Z0-9-]+)', upper)
    if perform_match:
        target = perform_match.group(1)
        if target not in ["UNTIL", "VARYING"]:
            return {
                "operation": "PERFORM",
                "target": target
            }

    accept_match = re.match(r'ACCEPT\s+([A-Z0-9-]+)', upper)
    if accept_match:
        return {
            "operation": "ACCEPT",
            "target": accept_match.group(1)
        }

    if upper.startswith("DISPLAY "):
        return parse_display(line)

    open_match = re.match(r'OPEN\s+([A-Z-]+)\s+([A-Z0-9-]+)', upper)
    if open_match:
        return {
            "operation": "OPEN",
            "mode": open_match.group(1),
            "file": open_match.group(2)
        }

    close_match = re.match(r'CLOSE\s+([A-Z0-9-]+)', upper)
    if close_match:
        return {
            "operation": "CLOSE",
            "file": close_match.group(1)
        }

    read_match = re.match(r'READ\s+([A-Z0-9-]+)', upper)
    if read_match:
        return {
            "operation": "READ",
            "file": read_match.group(1)
        }

    write_match = re.match(r'WRITE\s+([A-Z0-9-]+)', upper)
    if write_match:
        return {
            "operation": "WRITE",
            "record": write_match.group(1)
        }

    rewrite_match = re.match(r'REWRITE\s+([A-Z0-9-]+)', upper)
    if rewrite_match:
        return {
            "operation": "REWRITE",
            "record": rewrite_match.group(1)
        }

    if upper == "CONTINUE":
        return {"operation": "CONTINUE"}

    if "EXIT PARAGRAPH" in upper:
        return {"operation": "EXIT_PARAGRAPH"}

    if upper == "EXIT":
        return {"operation": "EXIT"}

    if "STOP RUN" in upper:
        return {"operation": "STOP_RUN"}

    return None


def normalize_continuation_lines(lines):
    """Join simple COBOL continuation statements before operation parsing."""
    normalized = []
    i = 0
    operation_starters = (
        "DISPLAY ",
        "ACCEPT ",
        "MOVE ",
        "ADD ",
        "SUBTRACT ",
        "COMPUTE ",
        "PERFORM ",
        "IF ",
        "EVALUATE ",
        "READ ",
        "WRITE ",
        "REWRITE ",
        "OPEN ",
        "CLOSE ",
        "STOP RUN",
        "EXIT",
    )

    while i < len(lines):
        current = clean_line(lines[i])
        upper = current.upper()

        if upper.startswith("COMPUTE ") and upper.endswith("="):
            parts = [current]
            i += 1
            while i < len(lines):
                next_line = clean_line(lines[i])
                next_upper = next_line.upper()
                if next_upper.startswith(operation_starters):
                    i -= 1
                    break
                if next_line:
                    parts.append(next_line)
                if next_line.endswith("."):
                    break
                i += 1
            normalized.append(" ".join(parts))
        else:
            normalized.append(lines[i])

        i += 1

    return normalized


def split_if_block(block_lines):
    true_lines = []
    false_lines = []
    current = "true"

    for line in block_lines:
        upper = clean_line(line).upper()

        if upper.startswith("ELSE"):
            current = "false"
            continue

        if upper.startswith("END-IF"):
            continue

        if current == "true":
            true_lines.append(line)
        else:
            false_lines.append(line)

    return true_lines, false_lines


def extract_if_blocks(lines):
    """
    Extract simple IF ... ELSE ... END-IF blocks.
    This is still rule-based MVP, not a full COBOL parser.
    """
    blocks = []
    i = 0

    while i < len(lines):
        line = clean_line(lines[i])
        upper = line.upper()

        if upper.startswith("IF "):
            condition = upper[3:].strip()

            block_lines = []
            depth = 1
            j = i + 1

            while j < len(lines):
                next_upper = clean_line(lines[j]).upper()

                if next_upper.startswith("IF "):
                    depth += 1

                if next_upper.startswith("END-IF"):
                    depth -= 1
                    if depth == 0:
                        break

                block_lines.append(lines[j])
                j += 1

            true_lines, false_lines = split_if_block(block_lines)

            blocks.append({
                "condition": parse_condition(condition),
                "true_branch": [
                    op for op in (parse_operation_line(x) for x in true_lines)
                    if op is not None
                ],
                "false_branch": [
                    op for op in (parse_operation_line(x) for x in false_lines)
                    if op is not None
                ]
            })

            i = j

        i += 1

    return blocks


def extract_file_operation_blocks(lines):
    blocks = []
    i = 0

    while i < len(lines):
        upper = clean_line(lines[i]).upper()

        if upper.startswith(("READ ", "WRITE ", "REWRITE ")):
            base_op = parse_operation_line(lines[i])
            if not base_op:
                i += 1
                continue

            invalid_key = []
            not_invalid_key = []
            current_branch = None

            j = i + 1

            while j < len(lines):
                next_upper = clean_line(lines[j]).upper()

                if next_upper.startswith(("END-READ", "END-WRITE", "END-REWRITE")):
                    break

                if next_upper.startswith("INVALID KEY"):
                    current_branch = "invalid"
                    remainder = next_upper.replace("INVALID KEY", "").strip()
                    if remainder:
                        op = parse_operation_line(remainder)
                        if op:
                            invalid_key.append(op)
                    j += 1
                    continue

                if next_upper.startswith("NOT INVALID KEY"):
                    current_branch = "not_invalid"
                    remainder = next_upper.replace("NOT INVALID KEY", "").strip()
                    if remainder:
                        op = parse_operation_line(remainder)
                        if op:
                            not_invalid_key.append(op)
                    j += 1
                    continue

                op = parse_operation_line(lines[j])
                if op:
                    if current_branch == "invalid":
                        invalid_key.append(op)
                    elif current_branch == "not_invalid":
                        not_invalid_key.append(op)

                j += 1

            if invalid_key:
                base_op["invalid_key"] = invalid_key

            if not_invalid_key:
                base_op["not_invalid_key"] = not_invalid_key

            blocks.append(base_op)
            i = j

        i += 1

    return blocks


def extract_evaluate_blocks(lines):
    rules = []
    i = 0

    while i < len(lines):
        upper = clean_line(lines[i]).upper()

        if upper.startswith("EVALUATE "):
            subject = upper.replace("EVALUATE", "", 1).strip()
            cases = []

            j = i + 1
            current_case = None

            while j < len(lines):
                next_line = clean_line(lines[j])
                next_upper = next_line.upper()

                if next_upper.startswith("END-EVALUATE"):
                    if current_case:
                        cases.append(current_case)
                    break

                when_match = re.match(r"WHEN\s+(.+)", next_upper)
                if when_match:
                    if current_case:
                        cases.append(current_case)

                    current_case = {
                        "when": when_match.group(1).strip().strip('"'),
                        "actions": []
                    }

                    # Handle one-line WHEN 1 PERFORM X
                    remainder = when_match.group(1).strip()
                    if " PERFORM " in remainder:
                        parts = remainder.split(" PERFORM ")
                        current_case["when"] = parts[0].strip().strip('"')
                        current_case["actions"].append({
                            "operation": "PERFORM",
                            "target": parts[1].strip()
                        })

                    j += 1
                    continue

                if current_case:
                    op = parse_operation_line(lines[j])
                    if op:
                        current_case["actions"].append(op)

                j += 1

            rules.append({
                "operation": "EVALUATE",
                "subject": subject,
                "cases": cases
            })

            i = j

        i += 1

    return rules


def extract_simple_operations(lines):
    lines = normalize_continuation_lines(lines)
    operations = []
    skip_keywords = (
        "IF ",
        "ELSE",
        "END-IF",
        "EVALUATE ",
        "WHEN ",
        "END-EVALUATE",
        "INVALID KEY",
        "NOT INVALID KEY",
        "END-READ",
        "END-WRITE",
        "END-REWRITE"
    )

    for line in lines:
        upper = clean_line(line).upper()

        if upper.startswith(skip_keywords):
            continue

        op = parse_operation_line(line)
        if op:
            operations.append(op)

    return operations


def add_rule_metadata(rule):
    paragraph = rule.get("paragraph", "")

    if paragraph == "LOGIN":
        rule["business_category"] = "authentication"
    elif paragraph in ["DEPOSIT", "WITHDRAW", "CHECK-BALANCE"]:
        rule["business_category"] = "financial_transaction"
    elif paragraph in ["CREATE-ACCOUNT", "GENERATE-ACCOUNT"]:
        rule["business_category"] = "account_onboarding"
    else:
        rule["business_category"] = "program_control"

    translation_map = {
        "MOVE": "python_assignment",
        "ADD": "python_addition",
        "SUBTRACT": "python_subtraction",
        "COMPUTE": "python_expression",
        "IF": "python_if_statement",
        "EVALUATE": "python_match_or_if_elif",
        "PERFORM": "python_function_call",
        "PERFORM_UNTIL": "python_while_loop",
        "READ": "file_read_operation",
        "WRITE": "file_create_operation",
        "REWRITE": "file_update_operation",
        "OPEN": "file_open_operation",
        "CLOSE": "file_close_operation",
        "ACCEPT": "input_operation",
        "DISPLAY": "output_operation",
        "STOP_RUN": "program_exit"
    }

    rule["translation_hint"] = translation_map.get(rule.get("type"), "manual_review")

    if paragraph in ["WITHDRAW", "DEPOSIT"] or rule.get("type") in ["WRITE", "REWRITE", "READ"]:
        rule["risk"] = "high"
    elif paragraph == "LOGIN":
        rule["risk"] = "medium"
    else:
        rule["risk"] = "low"

    rule["needs_ai_enrichment"] = True
    rule["ai_enrichment_targets"] = [
        "business_meaning",
        "risk_reason",
        "test_hints",
        "translation_notes"
    ]
    return rule


def operation_to_rule(operation, paragraph, rule_id):
    rule = {
        "rule_id": f"R{rule_id:03d}",
        "paragraph": paragraph,
        "type": operation.pop("operation")
    }

    rule.update(operation)
    return add_rule_metadata(rule)


def build_rule_ir(cobol_path, paragraph_map_path):
    content = read_cobol_file(cobol_path)
    paragraph_map = read_json(paragraph_map_path)

    all_rules = []
    rule_counter = 1

    for paragraph_name, meta in paragraph_map.items():
        lines = extract_paragraph_body(
            content,
            meta["start_line"],
            meta["end_line"]
        )

        # Extract structured IF blocks
        for if_block in extract_if_blocks(lines):
            rule = {
                "rule_id": f"R{rule_counter:03d}",
                "paragraph": paragraph_name,
                "type": "IF",
                "condition": if_block["condition"],
                "true_branch": if_block["true_branch"],
                "false_branch": if_block["false_branch"]
            }
            all_rules.append(add_rule_metadata(rule))
            rule_counter += 1

        # Extract structured EVALUATE blocks
        for evaluate in extract_evaluate_blocks(lines):
            rule = {
                "rule_id": f"R{rule_counter:03d}",
                "paragraph": paragraph_name,
                "type": "EVALUATE",
                "subject": evaluate["subject"],
                "cases": evaluate["cases"]
            }
            all_rules.append(add_rule_metadata(rule))
            rule_counter += 1

        # Extract structured READ/WRITE/REWRITE with INVALID KEY branches
        for file_op in extract_file_operation_blocks(lines):
            all_rules.append(operation_to_rule(file_op, paragraph_name, rule_counter))
            rule_counter += 1

        # Extract simple standalone operations
        for operation in extract_simple_operations(lines):
            # Avoid duplicating READ/WRITE/REWRITE already extracted as blocks
            if operation["operation"] in ["READ", "WRITE", "REWRITE"]:
                continue

            all_rules.append(operation_to_rule(operation, paragraph_name, rule_counter))
            rule_counter += 1

    return {
        "program": "ATM-MACHINE",
        "schema_version": "0.2",
        "rules": all_rules
    }


def save_rule_ir(cobol_path, paragraph_map_path, output_path):
    rule_ir = build_rule_ir(cobol_path, paragraph_map_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rule_ir, f, indent=2)

    return rule_ir


if __name__ == "__main__":
    cobol_path = "data/cobol/ATM.cob"
    paragraph_map_path = "outputs/paragraph_map.json"
    output_path = "outputs/rule_ir.json"

    result = save_rule_ir(cobol_path, paragraph_map_path, output_path)

    print("Generated outputs/rule_ir.json")
    print(json.dumps(result, indent=2))
