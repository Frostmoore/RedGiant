from formatter import money
from generator import report


def test_money_rounds():
    assert money(19.999) == "EUR 20.00"


def test_money_half_cent():
    assert money(0.005) == "EUR 0.01"


def test_report_totals():
    out = report([("a", 10.004), ("b", 0.006)])
    assert "TOTAL: EUR 10.01" in out
