import json
import re


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def python_safe_name(name):
    return name.lower().replace("-", "_")


def build_data_layout(program_structure_path, symbol_table_path, output_path):
    program_structure = read_json(program_structure_path)
    symbol_table = read_json(symbol_table_path)

    files = {}

    for file_info in program_structure.get("files", []):
        select_name = file_info["select_name"]

        record_name = None
        for name, meta in symbol_table.items():
            if meta.get("kind") == "record" and meta.get("section") == "FILE SECTION":
                record_name = name
                break

        fields = []
        current_position = 0

        if record_name:
            children = symbol_table[record_name].get("children", [])

            for child in children:
                meta = symbol_table[child]
                length = meta.get("length", 0)

                field = {
                    "name": child,
                    "python_name": meta.get("python_name", python_safe_name(child)),
                    "pic": meta.get("pic"),
                    "type": meta.get("python_type"),
                    "start": current_position,
                    "end": current_position + length,
                    "length": length,
                    "scale": meta.get("scale", 0)
                }

                if meta.get("padding"):
                    field["padding"] = meta["padding"]

                if meta.get("semantic_role"):
                    field["semantic_role"] = meta["semantic_role"]

                fields.append(field)
                current_position += length

        files[select_name] = {
            "assign_to": file_info.get("assign_to"),
            "organization": file_info.get("organization"),
            "access_mode": file_info.get("access_mode"),
            "record_key": file_info.get("record_key"),
            "file_status": file_info.get("file_status"),
            "record_name": record_name,
            "record_length": current_position,
            "storage_encoding": "fixed-width",
            "serialization": "indexed-record",
            "fields": fields
        }

    data_layout = {"files": files}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_layout, f, indent=2)

    return data_layout


if __name__ == "__main__":
    result = build_data_layout(
        "outputs/program_structure.json",
        "outputs/symbol_table.json",
        "outputs/data_layout.json"
    )

    print("Generated outputs/data_layout.json")
    print(json.dumps(result, indent=2))