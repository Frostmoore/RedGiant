from models import Account


def deposit(account: Account, amount: float) -> float:
    account.put(amount)
    return account.balance
