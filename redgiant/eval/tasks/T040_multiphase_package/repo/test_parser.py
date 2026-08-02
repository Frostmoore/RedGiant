import pytest

from parser import parse_line, parse_file


def test_parse_line_basic():
    assert parse_line("apple,3,1.50") == {"name": "apple", "qty": 3, "price": 1.5}


def test_parse_line_strips_spaces():
    assert parse_line("  pear , 2 , 0.75 ") == {"name": "pear", "qty": 2,
                                                "price": 0.75}


def test_parse_line_integer_price():
    assert parse_line("plum,1,2") == {"name": "plum", "qty": 1, "price": 2.0}


def test_parse_line_invalid_field_count():
    with pytest.raises(ValueError):
        parse_line("only,two")


def test_parse_line_invalid_numbers():
    with pytest.raises(ValueError):
        parse_line("apple,many,1.0")


def test_parse_file_skips_blank_lines(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("apple,3,1.50\n\npear,2,0.75\n", encoding="utf-8")
    rows = parse_file(str(p))
    assert [r["name"] for r in rows] == ["apple", "pear"]
