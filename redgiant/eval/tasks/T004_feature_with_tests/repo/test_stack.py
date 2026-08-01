import pytest

from stack import Stack


def test_push_pop():
    s = Stack()
    s.push(1)
    assert s.pop() == 1


def test_peek_returns_top_without_removing():
    s = Stack()
    s.push(1)
    s.push(2)
    assert s.peek() == 2
    assert len(s) == 2


def test_peek_empty_raises():
    s = Stack()
    with pytest.raises(IndexError):
        s.peek()
