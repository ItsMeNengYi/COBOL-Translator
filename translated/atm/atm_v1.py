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
ws_amount = Decimal('0')
ws_found = 'N'

# generated functions
def main_procedure():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    try:
        globals()["userdata_file"] = open('atm_accounts.dat', 'a+')
        ws_file_status = "00"
    except OSError:
        ws_file_status = "35"
    if ws_file_status == "35":
        try:
            globals()["userdata_file"] = open('atm_accounts.dat', 'w+')
            ws_file_status = "00"
        except OSError:
            ws_file_status = "35"
        _userdata_file = globals().get("userdata_file")
        if _userdata_file:
            _userdata_file.close()
        ws_file_status = "00"
        try:
            globals()["userdata_file"] = open('atm_accounts.dat', 'a+')
            ws_file_status = "00"
        except OSError:
            ws_file_status = "35"
    while ws_main_choice != 3:
        ws_main_choice = 0
        print(' ')
        print('===== ATM SYSTEM =====')
        print('1 - CREATE ACCOUNT')
        print('2 - LOGIN')
        print('3 - EXIT')
        while ws_main_choice < 1 or ws_main_choice > 3:
            print('ENTER CHOICE:')
            _raw_input = input()
            try:
                ws_main_choice = int(_raw_input)
            except Exception:
                ws_main_choice = 0
            if ws_main_choice < 1 or ws_main_choice > 3:
                print('INVALID CHOICE')
                print('PLEASE ENTER 1, 2, OR 3')
        if ws_main_choice == 1:
            create_account()
        elif ws_main_choice == 2:
            login()
        elif ws_main_choice == 3:
            print('GOODBYE')
    _userdata_file = globals().get("userdata_file")
    if _userdata_file:
        _userdata_file.close()
    ws_file_status = "00"
    raise SystemExit(0)

def create_account():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    f_name = ""
    f_age = 0
    f_pin = 0
    print('ENTER NAME:')
    f_name = input()
    if f_name == "":
        print('NAME CANNOT BE EMPTY')
        return
    print('ENTER AGE:')
    _raw_input = input()
    try:
        f_age = int(_raw_input)
    except Exception:
        f_age = 0
    if f_age < 18:
        print('YOU MUST BE AT LEAST 18 YEARS OLD')
        return
    while f_pin < 100000:
        print('CREATE 6-DIGIT PIN:')
        _raw_input = input()
        try:
            f_pin = int(_raw_input)
        except Exception:
            f_pin = 0
        if f_pin < 100000:
            print('PIN MUST BE 6 DIGITS')
    generate_account()
    f_bal = Decimal("0.00")
    _userdata_records = globals().setdefault("userdata_records", {})
    _userdata_records[f_account] = {'f_account': f_account, 'f_pin': f_pin, 'f_bal': f_bal, 'f_name': f_name, 'f_age': f_age}
    ws_file_status = "00"
    print('ACCOUNT CREATED SUCCESSFULLY')
    print('YOUR ACCOUNT NUMBER IS:')
    print(f_account)

def generate_account():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    _userdata_records = globals().setdefault("userdata_records", {})
    _random = __import__("random")
    while True:
        f_account = _random.randint(1000000000, 9999999999)
        if f_account not in _userdata_records:
            ws_file_status = "23"
            break

def login():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_found = 'N'
    ws_account = 0
    ws_pin = 0
    while ws_account <= 0:
        print('ENTER ACCOUNT NUMBER:')
        _raw_input = input()
        try:
            ws_account = int(_raw_input)
        except Exception:
            ws_account = 0
        if ws_account <= 0:
            print('INVALID ACCOUNT NUMBER')
    f_account = ws_account
    _userdata_records = globals().setdefault("userdata_records", {})
    _record = _userdata_records.get(f_account)
    if _record is None:
        ws_file_status = "23"
        ws_found = 'N'
    else:
        ws_file_status = "00"
        f_account = _record.get('f_account', f_account)
        f_pin = _record.get('f_pin', f_pin)
        f_bal = _record.get('f_bal', f_bal)
        f_name = _record.get('f_name', f_name)
        f_age = _record.get('f_age', f_age)
        ws_found = 'Y'
    if ws_found == 'N':
        print('ACCOUNT NOT FOUND')
    else:
        while ws_pin < 100000:
            print('ENTER PIN:')
            _raw_input = input()
            try:
                ws_pin = int(_raw_input)
            except Exception:
                ws_pin = 0
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
        _raw_input = input()
        try:
            ws_choice = int(_raw_input)
        except Exception:
            ws_choice = 0
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

def deposit():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_amount = Decimal("0.00")
    while ws_amount <= 0:
        print('ENTER DEPOSIT AMOUNT:')
        _raw_input = input()
        try:
            ws_amount = Decimal(_raw_input)
        except Exception:
            ws_amount = Decimal("0.00")
        if ws_amount <= 0:
            print('INVALID AMOUNT')
            print('AMOUNT MUST BE POSITIVE')
    f_bal += ws_amount
    _userdata_records = globals().setdefault("userdata_records", {})
    _userdata_records[f_account] = {'f_account': f_account, 'f_pin': f_pin, 'f_bal': f_bal, 'f_name': f_name, 'f_age': f_age}
    ws_file_status = "00"
    print('DEPOSIT SUCCESSFUL')
    print('NEW BALANCE:')
    print(f_bal)

def withdraw():
    global f_account, f_pin, f_bal, f_name, f_age, ws_file_status, ws_main_choice, ws_choice, ws_account, ws_pin, ws_amount, ws_found

    ws_amount = Decimal("0.00")
    while ws_amount <= 0:
        print('ENTER WITHDRAW AMOUNT:')
        _raw_input = input()
        try:
            ws_amount = Decimal(_raw_input)
        except Exception:
            ws_amount = Decimal("0.00")
        if ws_amount <= 0:
            print('INVALID AMOUNT')
            print('AMOUNT MUST BE POSITIVE')
    if ws_amount > f_bal:
        print('INSUFFICIENT BALANCE')
    else:
        f_bal -= ws_amount
        _userdata_records = globals().setdefault("userdata_records", {})
        _userdata_records[f_account] = {'f_account': f_account, 'f_pin': f_pin, 'f_bal': f_bal, 'f_name': f_name, 'f_age': f_age}
        ws_file_status = "00"

if __name__ == "__main__":
    main_procedure()
