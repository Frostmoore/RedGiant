from string_utils import initials, slugify, truncate


def test_slug_spaces_become_hyphens():  # il test rosso
    assert slugify("hello world") == "hello-world"


def test_slug_lowercases():
    assert slugify("HELLO") == "hello"


def test_slug_dots():
    assert slugify("a.b.c") == "a-b-c"


def test_slug_collapses_runs():
    assert slugify("a--b__c") == "a-b-c"


def test_slug_strips_edges():
    assert slugify("!hello!") == "hello"


def test_slug_numbers_kept():
    assert slugify("v2.0.1") == "v2-0-1"


def test_truncate_short():
    assert truncate("abc", 5) == "abc"


def test_truncate_long():
    assert truncate("abcdef", 4) == "abc…"


def test_truncate_exact():
    assert truncate("abcd", 4) == "abcd"


def test_initials_basic():
    assert initials("ada lovelace") == "AL"


def test_initials_extra_spaces():
    assert initials("  grace   hopper ") == "GH"
