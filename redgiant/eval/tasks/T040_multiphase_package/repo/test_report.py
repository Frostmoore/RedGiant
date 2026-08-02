import pytest

from report import format_summary


ROWS = [{"name": "apple", "qty": 3, "price": 1.5},
        {"name": "pear", "qty": 2, "price": 0.75},
        {"name": "apple", "qty": 1, "price": 1.5}]


def test_one_line_per_aggregated_name_plus_total():
    lines = format_summary(ROWS).splitlines()
    assert len(lines) == 3                       # apple, pear, TOTAL


def test_line_format_name_qty_value():
    lines = format_summary(ROWS).splitlines()
    assert lines[0] == "apple x4 = 6.00"
    assert lines[1] == "pear x2 = 1.50"


def test_total_line_last_with_two_decimals():
    lines = format_summary(ROWS).splitlines()
    assert lines[-1] == "TOTAL: 7.50"


def test_names_sorted_alphabetically():
    rows = [{"name": "zeta", "qty": 1, "price": 1.0},
            {"name": "alfa", "qty": 1, "price": 2.0}]
    lines = format_summary(rows).splitlines()
    assert lines[0].startswith("alfa") and lines[1].startswith("zeta")


def test_empty_rows():
    assert format_summary([]) == "TOTAL: 0.00"


def test_discounted_report_uses_transform():
    from transform import apply_discount
    lines = format_summary(apply_discount(ROWS, 50)).splitlines()
    assert lines[-1] == "TOTAL: 3.75"
