class Account:
    def __init__(self, balance=0.0):
        self.balance = balance

    def put(self, amount):
        self.balance += amount
