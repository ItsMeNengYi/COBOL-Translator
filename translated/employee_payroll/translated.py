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
    # TODO unsupported operation: ACCEPT EMP-NAME
    print('ENTER HOURS:')
    # TODO unsupported operation: ACCEPT HOURS-WORKED
    print('ENTER RATE:')
    # TODO unsupported operation: ACCEPT HOURLY-RATE
    gross_pay = hours_worked * hourly_rate
    print('EMPLOYEE: ' + f'{emp_name:<20}')
    print('GROSS PAY: ' + f'{gross_pay:08.2f}')
    raise SystemExit(0)

if __name__ == "__main__":
    main()
