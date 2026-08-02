from main import title_line
from util import slug


def test_slug_lowercases_and_hyphenates():
    assert slug("Hello World") == "hello-world"


def test_slug_strips():
    assert slug("  Hi  ") == "hi"


def test_title_line_uses_slug():
    assert title_line("My Post") == "My Post | my-post"
