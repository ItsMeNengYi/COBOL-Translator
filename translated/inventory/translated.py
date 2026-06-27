from decimal import Decimal

# variable declarations
stock = 0
order_qty = 0

# generated functions
def main():
    global stock, order_qty

    print('CURRENT STOCK:')
    # TODO unsupported operation: ACCEPT STOCK
    print('ORDER QUANTITY:')
    # TODO unsupported operation: ACCEPT ORDER-QTY
    if order_qty <= stock:
        stock -= order_qty
        print('ORDER APPROVED')
        print('REMAINING: ' + str(stock))
    else:
        print('INSUFFICIENT STOCK')
    raise SystemExit(0)

if __name__ == "__main__":
    main()
