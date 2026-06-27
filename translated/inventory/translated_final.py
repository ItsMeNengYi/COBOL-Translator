from decimal import Decimal

# variable declarations
stock = 0
order_qty = 0

# generated functions
def main():
    global stock, order_qty

    print('CURRENT STOCK:')
    _raw_input = input()
    try:
        stock = int(_raw_input)
    except Exception:
        stock = 0
    print('ORDER QUANTITY:')
    _raw_input = input()
    try:
        order_qty = int(_raw_input)
    except Exception:
        order_qty = 0
    if order_qty <= stock:
        stock -= order_qty
        print('ORDER APPROVED')
        print('REMAINING: ' + str(stock))
    else:
        print('INSUFFICIENT STOCK')
    raise SystemExit(0)

if __name__ == "__main__":
    main()
