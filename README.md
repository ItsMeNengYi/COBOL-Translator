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
- semantic_enrichment.json
- program_summary.md

## Technologies

- Python
- Regular Expressions
- OpenAI API
- JSON

##end


# Understanding `program_summary.md`

`program_summary.md` is a human-readable report automatically generated from the parser outputs and AI semantic enrichment pipeline. Its purpose is to transform machine-readable JSON representations of a COBOL program into an explanation that developers, translators, verifiers, and stakeholders can easily understand.

Rather than reading hundreds or thousands of lines of COBOL code, users can quickly understand the system's functionality, business rules, data structures, and migration considerations.

---

## 1. Overview

### Generated From

* `program_structure.json`
* `semantic_enrichment.json`

### Purpose

This section answers:

> **"What kind of system is this?"**

Example:

```text
Domain: Banking

Functions:
- Account creation
- Login
- Deposit
- Withdrawal
```

This provides a high-level understanding of the legacy application domain and business purpose.

---

## 2. Program Structure

### Generated From

* `program_structure.json`

### Purpose

This section answers:

> **"How is this COBOL program organized?"**

It provides:

* Source file name
* Programming language and dialect
* Program entry point
* Program type
* Divisions detected
* Number of paragraphs
* Number of files

This acts as the table of contents for the COBOL application.

---

## 3. Main Paragraphs

### Generated From

* `paragraph_map.json`
* `control_flow.json`

### Purpose

This section answers:

> **"What business functions exist?"**

Examples:

```text
CREATE-ACCOUNT
    → Create bank account

LOGIN
    → Authenticate customer

WITHDRAW
    → Process withdrawal transaction
```

This provides a business-oriented view of the COBOL program structure.

---

## 4. File Layout

### Generated From

* `data_layout.json`

### Purpose

This section answers:

> **"How is the data stored?"**

Example:

```text
USERDATA
    Storage: Indexed File
    Access: Random
    Record Key: F-ACCOUNT
```

This information is essential for migration to modern storage systems such as:

* SQLite
* PostgreSQL
* MongoDB
* Cloud databases

---

## 5. Important Business Rules

### Generated From

* `rule_ir.json`
* `semantic_enrichment.json`

### Purpose

This section answers:

> **"What business policies does this system enforce?"**

Examples:

```text
- User age must be at least 18.
- PIN must contain 6 digits.
- Withdrawal cannot exceed account balance.
```

This converts low-level COBOL logic into understandable business requirements.

---

## 6. Important Data Fields

### Generated From

* `symbol_table.json`
* `semantic_enrichment.json`

### Purpose

This section answers:

> **"What information does the system manage?"**

Examples:

```text
F-BAL
    → Account Balance

F-PIN
    → Authentication PIN

F-NAME
    → Customer Name
```

This section provides semantic understanding of variables beyond their original COBOL names.

---

## 7. Extraction Statistics

### Generated From

* `symbol_table.json`
* `rule_ir.json`
* `control_flow.json`

### Purpose

This section answers:

> **"How complex is this COBOL program?"**

Examples:

* Total variables extracted
* Total business rules extracted
* Control-flow nodes
* Control-flow edges
* Number of loops detected

These metrics help estimate migration complexity.

---

## 8. Translation Notes

### Generated From

* `semantic_enrichment.json`

### Purpose

This section provides guidance for the translation and verification stages.

Examples:

```text
- Use Python Decimal instead of float for monetary values.
- Preserve fixed-width COBOL strings.
- Maintain INVALID KEY handling semantics.
- Abstract DISPLAY and ACCEPT for automated testing.
```

---

# Why is `program_summary.md` Important?

`program_summary.md` acts as the bridge between:

```text
Machine-readable representation
                ↓
Human understanding
```

It allows engineers to understand a legacy COBOL system without reading the original COBOL source code.

---

# Usage by Other Teams

## Person 2 — Translator

Uses:

* Business Rules
* Translation Notes
* Data Fields
* File Layout

to generate:

```text
COBOL → Python/Java/C# translation
```

---

## Person 3 — Verification

Uses:

* Business Rules
* Statistics
* Risk Analysis

to generate:

```text
Test cases
Regression tests
Behavior verification
```

---

## Person 4 — Dashboard

Uses:

* Program Structure
* Business Rules
* Data Fields
* Control Flow

to generate:

```text
Interactive visualizations
Program dependency graphs
Migration dashboards
```

---

# Summary

`program_summary.md` is the human-readable explanation generated from the rule-based parser and AI semantic enrichment pipeline, allowing downstream translation, verification, and visualization components to understand the business semantics of legacy COBOL programs.
