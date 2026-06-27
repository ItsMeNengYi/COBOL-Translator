import re
import json


def read_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def read_cobol_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def extract_paragraph_body(content, start_line, end_line):
    lines = content.splitlines()
    return "\n".join(lines[start_line - 1:end_line])


def extract_perform_edges(paragraph_name, body):
    edges = []
    upper = body.upper()

    for match in re.finditer(r"\bPERFORM\s+([A-Z0-9-]+)", upper):
        target = match.group(1)

        if target in ["UNTIL", "VARYING"]:
            continue

        trigger = f"PERFORM {target}"

        if " UNTIL " in upper[match.start(): match.start() + 80]:
            trigger += " UNTIL condition"

        edges.append({
            "from": paragraph_name,
            "to": target,
            "trigger": trigger
        })

    return edges


def extract_evaluate_edges(paragraph_name, body):
    edges = []
    upper = body.upper()

    evaluate_blocks = re.finditer(
        r"EVALUATE\s+([A-Z0-9-]+)(.*?)(END-EVALUATE|\.)",
        upper,
        re.DOTALL
    )

    for block in evaluate_blocks:
        subject = block.group(1)
        block_text = block.group(2)

        when_matches = re.finditer(
            r"WHEN\s+([A-Z0-9\"'-]+).*?PERFORM\s+([A-Z0-9-]+)",
            block_text,
            re.DOTALL
        )

        for when in when_matches:
            value = when.group(1).replace('"', "")
            target = when.group(2)

            edges.append({
                "from": paragraph_name,
                "to": target,
                "trigger": f"EVALUATE {subject} WHEN {value}"
            })

    return edges


def extract_loops(paragraph_name, body):
    loops = []
    upper = body.upper()

    for match in re.finditer(r"PERFORM\s+UNTIL\s+(.+)", upper):
        raw_condition = match.group(1).strip()

        raw_condition = raw_condition.replace("IS EQUAL TO", "=")
        raw_condition = raw_condition.replace("IS GREATER THAN", ">")
        raw_condition = raw_condition.replace("IS LESS THAN", "<")

        condition_line = raw_condition.splitlines()[0].strip().rstrip(".")

        loops.append({
            "paragraph": paragraph_name,
            "type": "PERFORM_UNTIL",
            "condition_raw": condition_line
        })

    for match in re.finditer(r"PERFORM\s+VARYING\s+([A-Z0-9-]+).*?UNTIL\s+(.+)", upper):
        loops.append({
            "paragraph": paragraph_name,
            "type": "PERFORM_VARYING",
            "iterator": match.group(1),
            "condition_raw": match.group(2).splitlines()[0].strip().rstrip(".")
        })

    return loops


def build_control_flow(cobol_path, paragraph_map_path):
    content = read_cobol_file(cobol_path)
    paragraph_map = read_json(paragraph_map_path)

    nodes = list(paragraph_map.keys()) + ["EXIT_PROGRAM"]
    edges = []
    loops = []

    for paragraph_name, meta in paragraph_map.items():
        body = extract_paragraph_body(
            content,
            meta["start_line"],
            meta["end_line"]
        )

        edges.extend(extract_perform_edges(paragraph_name, body))
        edges.extend(extract_evaluate_edges(paragraph_name, body))
        loops.extend(extract_loops(paragraph_name, body))

    return {
        "entry_point": nodes[0] if nodes else None,
        "nodes": nodes,
        "edges": edges,
        "loops": loops
    }


def save_control_flow(cobol_path, paragraph_map_path, output_path):
    control_flow = build_control_flow(cobol_path, paragraph_map_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(control_flow, f, indent=2)

    return control_flow


if __name__ == "__main__":
    cobol_path = "data/cobol/ATM.cob"
    paragraph_map_path = "outputs/paragraph_map.json"
    output_path = "outputs/control_flow.json"

    control_flow = save_control_flow(
        cobol_path,
        paragraph_map_path,
        output_path
    )

    print("Generated outputs/control_flow.json")
    print(json.dumps(control_flow, indent=2))