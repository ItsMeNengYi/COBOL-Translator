import json
import os
from dotenv import load_dotenv
from openai import OpenAI


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_prompt(program_structure, symbol_table, rule_ir):
    important_rules = [
        rule for rule in rule_ir.get("rules", [])
        if rule.get("paragraph") in [
            "LOGIN",
            "CREATE-ACCOUNT",
            "DEPOSIT",
            "WITHDRAW"
        ]
        and rule.get("type") in [
            "IF",
            "ADD",
            "SUBTRACT",
            "READ",
            "WRITE",
            "REWRITE",
            "EVALUATE"
        ]
    ]

    compact_symbol_table = {
        name: {
            "pic": meta.get("pic"),
            "python_type": meta.get("python_type"),
            "section": meta.get("section")
        }
        for name, meta in symbol_table.items()
        if meta.get("pic")
    }

    return f"""
You are a COBOL modernization semantic analyst.

Infer business meaning from context. Do not rely only on variable names.
Return JSON only. Do not include markdown.

Program:
{json.dumps(program_structure, indent=2)}

Variables:
{json.dumps(compact_symbol_table, indent=2)}

Important rules:
{json.dumps(important_rules, indent=2)}

Return JSON with:
{{
  "program": "...",
  "detected_domain": "...",
  "variable_enrichment": {{
    "VARIABLE-NAME": {{
      "semantic_role": "...",
      "is_money": true,
      "confidence": "low/medium/high",
      "reason": "..."
    }}
  }},
  "business_rules": [
    {{
      "rule_id": "R001",
      "business_meaning": "...",
      "risk_level": "low/medium/high",
      "test_hints": ["..."],
      "translation_notes": "..."
    }}
  ],
  "overall_business_summary": "...",
  "migration_risks": ["..."]
}}
"""


def call_ai_agent(prompt):
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not found. Please create a .env file with OPENAI_API_KEY=your_key"
        )

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        timeout=60
    )

    return response.output_text


def build_semantic_enrichment():
    program_structure = read_json("outputs/program_structure.json")
    symbol_table = read_json("outputs/symbol_table.json")
    rule_ir = read_json("outputs/rule_ir.json")

    prompt = build_prompt(program_structure, symbol_table, rule_ir)
    ai_output = call_ai_agent(prompt)

    try:
        enriched_json = json.loads(ai_output)
    except json.JSONDecodeError:
        enriched_json = {
            "error": "AI output was not valid JSON",
            "raw_ai_output": ai_output
        }

    return enriched_json


if __name__ == "__main__":
    result = build_semantic_enrichment()
    write_json("outputs/semantic_enrichment.json", result)

    print("Generated outputs/semantic_enrichment.json")