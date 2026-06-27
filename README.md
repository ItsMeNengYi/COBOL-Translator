# COBOL-Translator
I set up a template based on `task.md`. The structure is not exactly the same because the instruction is inconsistent All Python files are currently empty placeholders. Feel free to change the folder structure however you like.

---

## How to run translator
```bash
python -m src.pipeline data/cobol/employee_payroll.cob
```

For any input file, outputs are grouped by the COBOL filename stem.
For example, `data/cobol/employee_payroll.cob` generates:

```text
outputs/employee_payroll/
  program_structure.json
  symbol_table.json
  paragraph_map.json
  control_flow.json
  data_layout.json
  rule_ir.json
  semantic_meaning.json
  program_summary.md
  translation_map.json

translated/employee_payroll/
  translated.py
  translated_final.py
```

## How to run test generator
```bash
python3 tests/test_generator.py --generate-only --max-cases 2
or
python3 tests/test_generator.py <generated_json>
or
python3 tests/test_generator.py --max-cases 2
```

## How to Run It

### 1. Install Docker

Download and install **Docker Desktop** (Windows or Mac). You don't need to install Python or COBOL on your actual computer.

### 2. Write Your Code

Add your logic to the python files.

### 3. Update the Script

Open `run.sh` and add your execution command under `# Put your command here`. 
*Example:* `python3 src/parser.py`

### 4. Test Your Code

Run these two commands in your terminal:

```bash
docker build -t cobol-translator .

```
for windows
```bash
docker run --rm -p 8501:8501 -v "${PWD}:/app" cobol-translator
```

for mac/linux

```bash
docker run --rm -p 8501:8501 -v "$(pwd)":/app cobol-translator 
```
