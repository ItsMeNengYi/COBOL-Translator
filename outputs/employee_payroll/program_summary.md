# Program Summary: PAYROLL

## Overview

`PAYROLL` is a COBOL ATM/account management program. It uses an indexed account file and supports account creation, login, balance inquiry, deposit, withdrawal, and logout.

## Program Structure

- Source file: `employee_payroll.cob`
- Language: COBOL
- Dialect: GnuCOBOL
- Entry point: `MAIN`
- Program type: interactive_banking_system
- Divisions detected: IDENTIFICATION, DATA, PROCEDURE
- Paragraph count: 1
- File count: 0

## Main Paragraphs

- `MAIN`: Purpose not inferred.


## File Layout



## Important Business Rules

- Main menu choice must be 1, 2, or 3.
- Account name cannot be empty.
- User age must be at least 18.
- PIN must be a 6-digit number.
- Login succeeds only when entered PIN matches the stored PIN.
- Deposit amount must be positive.
- Deposits increase account balance.
- Withdrawal amount must be positive.
- Withdrawal is rejected if amount exceeds balance.
- Successful withdrawals decrease account balance.


## Important Data Fields

- Money fields: 
- Total variables: 4
- Total rules extracted: 10
- Control-flow nodes: 2
- Control-flow edges: 0
- Loops detected: 0

## Notes for Translation and Verification

- Money-like fields must use `Decimal`, never `float`.
- COBOL names with hyphens should be mapped to Python-safe snake_case names.
- Fixed-width string fields such as `F-NAME PIC X(20)` should preserve or intentionally normalize trailing spaces.
- `USERDATA` is an indexed/random-access file keyed by `F-ACCOUNT`.
- `READ`, `WRITE`, and `REWRITE` branches with `INVALID KEY` and `NOT INVALID KEY` must be preserved.
- `DISPLAY` and `ACCEPT` are console I/O and can be abstracted for automated testing.
