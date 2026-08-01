import pytest

from api import deposit, withdraw
from models import Account


def test_deposit():
    a = Account()
    assert deposit(a, 50) == 50


def test_withdraw():
    a = Account(100)
    assert withdraw(a, 30) == 70


def test_withdraw_insufficient_funds():
    a = Account(10)
    with pytest.raises(ValueError):
        withdraw(a, 30)


def test_take_is_on_the_model():
    a = Account(5)
    a.take(2)
    assert a.balance == 3
