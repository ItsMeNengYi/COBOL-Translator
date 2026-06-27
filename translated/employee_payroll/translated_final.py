from decimal import Decimal

# variable declarations
emp_name = ""
hours_worked = 0
hourly_rate = Decimal("0.00")
gross_pay = Decimal("0.00")

# generated functions
def main():
    global emp_name, hours_worked, hourly_rate, gross_pay

    print('ENTER EMPLOYEE NAME:')
    emp_name = input()
    print('ENTER HOURS:')
    _raw_input = input()
    try:
        hours_worked = int(_raw_input)
    except Exception:
        hours_worked = 0
    print('ENTER RATE:')
    _raw_input = input()
    try:
        hourly_rate = Decimal(_raw_input)
    except Exception:
        hourly_rate = Decimal("0.00")
    gross_pay = hours_worked * hourly_rate
    print('EMPLOYEE: ' + f'{emp_name:<20}')
    print('GROSS PAY: ' + f'{gross_pay:08.2f}')
    raise SystemExit(0)

if __name__ == "__main__":
    main()
