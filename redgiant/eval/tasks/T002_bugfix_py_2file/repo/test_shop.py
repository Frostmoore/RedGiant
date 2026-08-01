from shop import final_price
from lib import apply_discount


def test_promo_gives_ten_percent_off():
    assert final_price(100) == 90.0


def test_lib_contract_unchanged():
    assert apply_discount(200, 50) == 100.0
