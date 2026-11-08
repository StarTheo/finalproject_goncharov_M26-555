"""Исключения приложения ValutaTrade Hub."""


class InsufficientFundsError(Exception):
    """Недостаточно средств для выполнения операции."""


class CurrencyNotFoundError(Exception):
    """Запрошенная валюта не поддерживается."""
