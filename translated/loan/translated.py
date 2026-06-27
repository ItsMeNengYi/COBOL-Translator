from decimal import Decimal

# variable declarations
salary = Decimal("0.00")
credit_score = 0
approved = 'N'

# generated functions
def main():
    global salary, credit_score, approved

    print('SALARY:')
    # TODO unsupported operation: ACCEPT SALARY
    print('CREDIT SCORE:')
    # TODO unsupported operation: ACCEPT CREDIT-SCORE
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
