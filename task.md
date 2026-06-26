COBOL Translator Project — Team Task Distribution

Person 1: COBOL Parser + Semantic Extractor

Main goal: understand the original COBOL program.

Tasks:

- Read the COBOL file.
- Detect main sections: IDENTIFICATION, DATA, WORKING-STORAGE, PROCEDURE DIVISION.
- Extract variables such as BALANCE, AMOUNT, PIN, STATUS.
- Extract paragraphs/functions such as LOGIN, WITHDRAW, DEPOSIT.
- Detect important COBOL logic:
  - IF / ELSE
  - EVALUATE / WHEN
  - PERFORM
  - MOVE
  - ADD / SUBTRACT / COMPUTE
  - READ / WRITE
- Generate a JSON semantic summary.

Output:

- "src/parser.py"
- "src/semantic_extractor.py"
- "outputs/semantic_summary.json"

Example output:

{
  "program": "ATM",
  "variables": ["BALANCE", "AMOUNT", "PIN"],
  "paragraphs": ["LOGIN", "WITHDRAW", "DEPOSIT"],
  "business_rules": [
    "User must enter correct PIN before transaction",
    "Deposit increases balance",
    "Withdrawal decreases balance only if balance is sufficient"
  ]
}

---

Person 2: COBOL to Python Translator

Main goal: translate COBOL logic into Python.

Tasks:

- Take the parsed COBOL paragraphs from Person 1.
- Translate paragraph-by-paragraph instead of translating the whole file at once.
- Use rule-based translation for simple COBOL commands:
  - MOVE → assignment
  - ADD → "+="
  - SUBTRACT → "-="
  - COMPUTE → expression
  - DISPLAY → print
- Use LLM translation for more complex logic:
  - nested IF
  - EVALUATE
  - PERFORM loops
  - file handling
- Make sure Python uses "Decimal" for money calculations.
- Save translated Python code.

Output:

- "src/translator.py"
- "src/llm_prompts.py"
- "translated/atm_translated.py"

Example output:

from decimal import Decimal

def withdraw(balance, amount):
    if balance >= amount:
        balance -= amount
        status = "SUCCESS"
    else:
        status = "INSUFFICIENT FUNDS"
    return balance, status

---

Person 3: Test Case Generator + Comparator

Main goal: prove the translated Python behaves the same as the original COBOL.

Tasks:

- Create manual ATM test cases first.
- Later add auto-generated test cases from COBOL logic.
- Run the original COBOL program using GnuCOBOL.
- Run the translated Python program using the same inputs.
- Compare COBOL output and Python output.
- Mark each test as PASS or FAIL.
- If failed, identify the mismatch.

Manual test cases:

- Valid deposit
- Valid withdrawal
- Withdrawal exceeds balance
- Invalid PIN
- Balance inquiry
- Amount equals balance
- Amount is zero
- Invalid transaction type

Output:

- "src/test_generator.py"
- "src/cobol_runner.py"
- "src/python_runner.py"
- "src/comparator.py"
- "data/test_cases.json"
- "outputs/test_results.json"

Example result:

{
  "test_id": "T003",
  "scenario": "Withdrawal exceeds balance",
  "input": {
    "balance": "100.00",
    "amount": "200.00",
    "transaction": "WITHDRAW"
  },
  "cobol_output": {
    "balance": "100.00",
    "status": "INSUFFICIENT FUNDS"
  },
  "python_output": {
    "balance": "100.00",
    "status": "INSUFFICIENT FUNDS"
  },
  "match": true
}

---

Person 4: Dashboard + Report Generator

Main goal: make the system easy to demo and understand.

Tasks:

- Build a Streamlit dashboard.
- Allow user to upload COBOL file.
- Show extracted business rules.
- Show translated Python code.
- Show test case results.
- Show mismatches clearly.
- Show final migration confidence score.
- Generate an HTML/PDF-style migration report.

Dashboard pages:

1. Upload COBOL
2. Semantic Explanation
3. Python Translation
4. Test Results
5. Mismatch Analysis
6. Final Report

Output:

- "app.py"
- "src/report_generator.py"
- "reports/migration_report.html"

Example dashboard result:

Program: ATM.cob
Business Rules Extracted: 8
Test Cases Run: 12
Passed: 11
Failed: 1
Migration Confidence: 91.7%

---

Integration Flow

COBOL file
↓
Person 1: Parser + semantic summary
↓
Person 2: Python translation
↓
Person 3: Run COBOL + Python and compare outputs
↓
Person 4: Dashboard + final report

Final Demo Flow

1. Upload "ATM.cob".
2. System explains the COBOL business logic.
3. System translates COBOL to Python.
4. System runs ATM test cases.
5. System compares COBOL output vs Python output.
6. System shows pass/fail result.
7. If mismatch exists, system explains where the translated code differs.
8. Final report is generated.

COBOL Semantic Migration & Verification Platform

cobol-semantic-migration/
│
├── README.md
├── requirements.txt
├── app.py                        # Streamlit dashboard
├── config.py
│
├── data/
│   ├── cobol/
│   │   ├── ATM.cob
│   │   ├── COPYBOOKS/
│   │   └── sample_programs/
│   │
│   ├── test_inputs/
│   │   ├── manual_tests.json
│   │   └── generated_tests.json
│   │
│   ├── expected_outputs/
│   │
│   ├── translated/
│   │
│   └── reports/
│
├── src/
│
│   ├── parser/
│   │   ├── parser.py
│   │   ├── lexer.py
│   │   ├── semantic_extractor.py
│   │   ├── control_flow.py
│   │   └── file_analyzer.py
│   │
│   ├── translator/
│   │   ├── translator.py
│   │   ├── rule_based.py
│   │   ├── llm_translator.py
│   │   ├── prompt.py
│   │   └── postprocessor.py
│   │
│   ├── validator/
│   │   ├── cobol_runner.py
│   │   ├── python_runner.py
│   │   ├── comparator.py
│   │   ├── test_generator.py
│   │   └── repair_agent.py
│   │
│   ├── ui/
│   │   ├── upload_page.py
│   │   ├── semantic_page.py
│   │   ├── translation_page.py
│   │   ├── validation_page.py
│   │   └── report_page.py
│   │
│   └── utils/
│       ├── logger.py
│       ├── helpers.py
│       └── json_utils.py
│
├── outputs/
│   ├── semantic_summary.json
│   ├── translated_python.py
│   ├── validation_results.json
│   ├── execution_trace.json
│   └── migration_report.html
│
├── docs/
│   ├── architecture.md
│   ├── pipeline.md
│   └── screenshots/
│
└── tests/
    ├── test_parser.py
    ├── test_translator.py
    ├── test_validator.py
    └── sample_cases.py

Responsibilities

Person 1

src/parser/

Person 2

src/translator/

Person 3

src/validator/

Person 4

src/ui/
app.py
reports/

Final Pipeline

Upload COBOL
        │
        ▼
Parser
        │
        ▼
Semantic Extractor
        │
        ▼
LLM Translator
        │
        ▼
Python Code
        │
        ├──────────────┐
        ▼              ▼
Run COBOL        Run Python
        │              │
        └──────┬───────┘
               ▼
      Compare Outputs
               │
      ┌────────┴────────┐
      │                 │
   Match             Mismatch
      │                 │
      ▼                 ▼
Generate Report     AI Repair
                         │
                         ▼
                  Re-run Validation