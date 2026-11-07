"""Модели пользователя, кошелька и портфеля."""

from decimal import Decimal

from valutatrade_hub.core.exceptions import InsufficientFundsError


class Wallet:
    """Кошелёк для хранения одной валюты."""

    def __init__(self, currency_code, balance=0.0):
        """Создаёт кошелёк с проверенным начальным балансом."""
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self):
        """Возвращает текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value):
        """Проверяет и устанавливает баланс."""
        if type(value) not in (int, float):
            raise ValueError("Баланс должен быть числом.")

        if not 0 <= value < float("inf"):
            raise ValueError("Баланс должен быть конечным неотрицательным числом.")

        self._balance = float(value)

    def deposit(self, amount):
        """Пополняет кошелёк на положительную сумму."""
        if type(amount) not in (int, float):
            raise ValueError("Сумма пополнения должна быть числом.")

        if not 0 < amount < float("inf"):
            raise ValueError("Сумма пополнения должна быть конечной и положительной.")

        self.balance = float(Decimal(str(self.balance)) + Decimal(str(amount)))

    def withdraw(self, amount):
        """Списывает положительную сумму при достаточном балансе."""
        if type(amount) not in (int, float):
            raise ValueError("Сумма списания должна быть числом.")

        if not 0 < amount < float("inf"):
            raise ValueError("Сумма списания должна быть конечной и положительной.")

        if amount > self.balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self.balance}, требуется {amount}."
            )

        self.balance = float(Decimal(str(self.balance)) - Decimal(str(amount)))
