from decimal import Decimal

# variable declarations
salary = Decimal("0.00")
credit_score = 0
approved = 'N'

# generated functions
def main():
    global salary, credit_score, approved

    print('SALARY:')
    _raw_input = input()
    try:
        salary = Decimal(_raw_input)
    except Exception:
        salary = Decimal("0.00")
    print('CREDIT SCORE:')
    _raw_input = input()
    try:
        credit_score = int(_raw_input)
    except Exception:
        credit_score = 0
    if salary >= Decimal("5000"):
        if credit_score >= 700:
            approved = 'Y'
    if approved == 'Y':
        print('LOAN APPROVED')
    else:
        print('LOAN REJECTED')
    raise SystemExit(0)

if __name__ == "__main__":
    main()
