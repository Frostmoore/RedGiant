from lib import apply_discount

PROMO_DISCOUNT = 0.1  # advertised as "10% off"


def final_price(price):
    return apply_discount(price, PROMO_DISCOUNT)
