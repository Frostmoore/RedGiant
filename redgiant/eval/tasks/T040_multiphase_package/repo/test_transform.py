import pytest

from transform import aggregate, apply_discount


ROWS = [{"name": "apple", "qty": 3, "price": 1.5},
        {"name": "pear", "qty": 2, "price": 0.75},
        {"name": "apple", "qty": 1, "price": 1.5}]


def test_aggregate_sums_quantities_by_name():
    agg = aggregate(ROWS)
    assert agg["apple"]["qty"] == 4 and agg["pear"]["qty"] == 2


def test_aggregate_computes_value():
    agg = aggregate(ROWS)
    assert agg["apple"]["value"] == pytest.approx(6.0)
    assert agg["pear"]["value"] == pytest.approx(1.5)


def test_aggregate_empty():
    assert aggregate([]) == {}


def test_apply_discount_scales_prices():
    out = apply_discount(ROWS, 10)
    assert out[0]["price"] == pytest.approx(1.35)
    assert ROWS[0]["price"] == pytest.approx(1.5)   # input non mutato


def test_apply_discount_zero_is_identity():
    out = apply_discount(ROWS, 0)
    assert [r["price"] for r in out] == [r["price"] for r in ROWS]


def test_apply_discount_invalid_pct():
    with pytest.raises(ValueError):
        apply_discount(ROWS, -5)
    with pytest.raises(ValueError):
        apply_discount(ROWS, 101)
