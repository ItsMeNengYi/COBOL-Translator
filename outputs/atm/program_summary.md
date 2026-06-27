# Program Summary: ATM-MACHINE

## Overview

`ATM-MACHINE` is a COBOL ATM/account management program. It uses an indexed account file and supports account creation, login, balance inquiry, deposit, withdrawal, and logout.

## Program Structure

- Source file: `ATM.cob`
- Language: COBOL
- Dialect: GnuCOBOL
- Entry point: `MAIN-PROCEDURE`
- Program type: interactive_banking_system
- Divisions detected: IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE
- Paragraph count: 8
- File count: 1

## Main Paragraphs

- `MAIN-PROCEDURE`: Open account file, handle main menu, route to account creation or login, then close file.
- `CREATE-ACCOUNT`: Collect name, age, PIN; validate inputs; generate account number; create account record.
- `GENERATE-ACCOUNT`: Generate random account number and retry if it already exists.
- `LOGIN`: Read account, validate existence and PIN, then enter ATM menu until logout.
- `ATM-MENU`: Show post-login menu and route to balance, deposit, withdraw, or logout.
- `CHECK-BALANCE`: Display current account balance.
- `DEPOSIT`: Accept positive deposit amount, add it to balance, and update account record.
- `WITHDRAW`: Accept positive withdrawal amount, check sufficient balance, subtract it, and update account record if valid.


## File Layout

- `USERDATA` assigned to `atm_accounts.dat`
  - Organization: INDEXED
  - Access mode: RANDOM
  - Record key: `F-ACCOUNT`
  - Record length: 50


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
- Total variables: 13
- Total rules extracted: 73
- Control-flow nodes: 9
- Control-flow edges: 20
- Loops detected: 8

## Notes for Translation and Verification

- Money-like fields must use `Decimal`, never `float`.
- COBOL names with hyphens should be mapped to Python-safe snake_case names.
- Fixed-width string fields such as `F-NAME PIC X(20)` should preserve or intentionally normalize trailing spaces.
- `USERDATA` is an indexed/random-access file keyed by `F-ACCOUNT`.
- `READ`, `WRITE`, and `REWRITE` branches with `INVALID KEY` and `NOT INVALID KEY` must be preserved.
- `DISPLAY` and `ACCEPT` are console I/O and can be abstracted for automated testing.
