from decimal import Decimal

# variable declarations
f_account = 0
f_pin = 0
f_bal = Decimal("0.00")
f_name = ""
f_age = 0
ws_file_status = ""
ws_main_choice = 0
ws_choice = 0
ws_account = 0
ws_pin = 0
ws_amount = Decimal("0.00")
ws_found = ""

# generated functions
def main_procedure():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    # TODO unsupported operation: OPEN USERDATA
    if ws_file_status == "35":
        # TODO unsupported operation: OPEN USERDATA
        # TODO unsupported operation: CLOSE USERDATA
        # TODO unsupported operation: OPEN USERDATA
    while ws_main_choice != 3:
        ws_main_choice = 0
        print(' ')
        print('===== ATM SYSTEM =====')
        print('1 - CREATE ACCOUNT')
        print('2 - LOGIN')
        print('3 - EXIT')
        while ws_main_choice < 1 or ws_main_choice > 3:
            print('ENTER CHOICE:')
            # TODO unsupported operation: ACCEPT WS-MAIN-CHOICE
            if ws_main_choice < 1 or ws_main_choice > 3:
                print('INVALID CHOICE')
                print('PLEASE ENTER 1, 2, OR 3')
        if ws_main_choice == 1:
            create_account()
        elif ws_main_choice == 2:
            login()
        elif ws_main_choice == 3:
            print('GOODBYE')
    # TODO unsupported operation: CLOSE USERDATA
    raise SystemExit(0)

def create_account():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    f_name = ""
    f_age = 0
    f_pin = 0
    print('ENTER NAME:')
    # TODO unsupported operation: ACCEPT F-NAME
    if f_name == "":
        print('NAME CANNOT BE EMPTY')
        return
    print('ENTER AGE:')
    # TODO unsupported operation: ACCEPT F-AGE
    if f_age < 18:
        print('YOU MUST BE AT LEAST 18 YEARS OLD')
        return
    while f_pin < 100000:
        print('CREATE 6-DIGIT PIN:')
        # TODO unsupported operation: ACCEPT F-PIN
        if f_pin < 100000:
            print('PIN MUST BE 6 DIGITS')
    generate_account()
    f_bal = Decimal("0.00")
    # TODO unsupported operation: WRITE F-DATA

def generate_account():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    # TODO unsupported operation: READ USERDATA
    pass

def login():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_found = 'N'
    ws_account = 0
    ws_pin = 0
    while ws_account <= 0:
        print('ENTER ACCOUNT NUMBER:')
        # TODO unsupported operation: ACCEPT WS-ACCOUNT
        if ws_account <= 0:
            print('INVALID ACCOUNT NUMBER')
    f_account = ws_account
    # TODO unsupported operation: READ USERDATA
    if ws_found == 'N':
        print('ACCOUNT NOT FOUND')
    else:
        while ws_pin < 100000:
            print('ENTER PIN:')
            # TODO unsupported operation: ACCEPT WS-PIN
            if ws_pin < 100000:
                print('PIN MUST BE 6 DIGITS')
        if ws_pin == f_pin:
            print('LOGIN SUCCESSFUL')
            print('WELCOME, ', f_name)
            ws_choice = 0
            while ws_choice != 4:
                atm_menu()
        else:
            print('WRONG PIN')
            print('PLEASE TRY AGAIN')

def atm_menu():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_choice = 0
    print(' ')
    print('===== ATM MENU =====')
    print('ACCOUNT: ', f_account)
    print('NAME: ', f_name)
    print('1 - CHECK BALANCE')
    print('2 - DEPOSIT')
    print('3 - WITHDRAW')
    print('4 - LOGOUT')
    while ws_choice < 1 or ws_choice > 4:
        print('ENTER CHOICE:')
        # TODO unsupported operation: ACCEPT WS-CHOICE
        if ws_choice < 1 or ws_choice > 4:
            print('INVALID CHOICE')
            print('PLEASE ENTER 1, 2, 3, OR 4')
    if ws_choice == 1:
        check_balance()
    elif ws_choice == 2:
        deposit()
    elif ws_choice == 3:
        withdraw()
    elif ws_choice == 4:
        print('LOGGING OUT')

def check_balance():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    print('CURRENT BALANCE:')
    print(str(f_bal))
    pass

def deposit():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_amount = Decimal("0.00")
    while ws_amount <= 0:
        print('ENTER DEPOSIT AMOUNT:')
        # TODO unsupported operation: ACCEPT WS-AMOUNT
        if ws_amount <= 0:
            print('INVALID AMOUNT')
            print('AMOUNT MUST BE POSITIVE')
    f_bal += ws_amount
    # TODO unsupported operation: REWRITE F-DATA

def withdraw():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_amount = Decimal("0.00")
    while ws_amount <= 0:
        print('ENTER WITHDRAW AMOUNT:')
        # TODO unsupported operation: ACCEPT WS-AMOUNT
        if ws_amount <= 0:
            print('INVALID AMOUNT')
            print('AMOUNT MUST BE POSITIVE')
    if ws_amount > f_bal:
        print('INSUFFICIENT BALANCE')
    else:
        f_bal -= ws_amount
        # TODO unsupported operation: REWRITE F-DATA

if __name__ == "__main__":
    main_procedure()
