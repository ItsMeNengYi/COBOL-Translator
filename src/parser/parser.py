from structure import save_program_structure
from symbol_table import save_symbol_table
from paragraph_map import save_paragraph_map
from control_flow import save_control_flow
from data_layout import build_data_layout
from rule_ir import save_rule_ir
from summary import build_summary, write_summary


def run_all():
    cobol_path = "data/cobol/ATM.cob"

    print("Running program structure extraction...")
    save_program_structure(cobol_path, "outputs/program_structure.json")

    print("Running symbol table extraction...")
    save_symbol_table(cobol_path, "outputs/symbol_table.json")

    print("Running paragraph map extraction...")
    save_paragraph_map(cobol_path, "outputs/paragraph_map.json")

    print("Running control flow extraction...")
    save_control_flow(
        cobol_path,
        "outputs/paragraph_map.json",
        "outputs/control_flow.json"
    )

    print("Running data layout extraction...")
    build_data_layout(
        "outputs/program_structure.json",
        "outputs/symbol_table.json",
        "outputs/data_layout.json"
    )

    print("Running rule IR extraction...")
    save_rule_ir(
        cobol_path,
        "outputs/paragraph_map.json",
        "outputs/rule_ir.json"
    )

    print("Generating program summary...")
    summary = build_summary()
    write_summary("outputs/program_summary.md", summary)

    print("All Person 1 outputs generated successfully.")


if __name__ == "__main__":
    run_all()