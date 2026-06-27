# COBOL-Translator

#sheryl
# COBOL Semantic Parser

## Objective
Build a hybrid rule-based + AI semantic extraction pipeline.

## Workflow

COBOL
    ↓
Rule-based Parser
    ↓
JSON Intermediate Representation
    ↓
AI Semantic Agent
    ↓
Enriched Semantic Representation

## Outputs

- program_structure.json
- symbol_table.json
- paragraph_map.json
- control_flow.json
- data_layout.json
- rule_ir.json
- semantic_meaning.json
- semantic_enrichment.json
- program_summary.md

## Run Commands

Run the full pipeline from one COBOL file into semantic meaning and final Python:

```bash
venv/bin/python -m src.pipeline data/cobol/ATM.cob
```

This generates:

```text
outputs/<input>_semantic_meaning.json
outputs/program_summary.md
outputs/rule_ir.json
translated/<input>_translated.py
translated/<input>_translated_final.py
```

For example, `data/cobol/employee_payroll.cob` generates
`translated/employee_payroll_translated.py` and
`translated/employee_payroll_translated_final.py`.

Run the same full pipeline with LLM fallback enabled:

```bash
venv/bin/python -m src.pipeline data/cobol/ATM.cob --use-llm
```

Generate the deterministic rule-based Python translation:

```bash
python3 src/translator/rule_based.py
```

Run the LLM fallback layer with the project virtual environment:

```bash
venv/bin/python -m src.translator.llm_fallback
```

Choose a translated input filename and output filename:

```bash
venv/bin/python -m src.translator.llm_fallback translated/atm_translated.py -o translated/atm_translated_final.py
```

Run deterministic fallback only, without calling the LLM:

```bash
venv/bin/python -m src.translator.llm_fallback translated/atm_translated.py -o translated/atm_translated_final.py --no-llm
```

Check whether the final translated file still contains unsupported TODO blocks:

```bash
grep -n "TODO unsupported" translated/atm_translated_final.py
```

Compile-check the generated final Python file:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/cobol_pycache venv/bin/python -m py_compile translated/atm_translated_final.py
```

Before running the LLM fallback, set your API key in `.env`:

```env
OPENAI_API_KEY=your_api_key_here
```

## Technologies

- Python
- Regular Expressions
- OpenAI API
- JSON

##end
