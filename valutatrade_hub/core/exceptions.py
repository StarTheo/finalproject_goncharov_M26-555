"""Исключения приложения ValutaTrade Hub."""


class InsufficientFundsError(Exception):
    """Недостаточно средств для выполнения операции."""


class CurrencyNotFoundError(Exception):
    """Запрошенная валюта не поддерживается."""


class StorageError(Exception):
    """Ошибка чтения или сохранения данных приложения."""


class AuthenticationError(Exception):
    """Ошибка проверки учётных данных пользователя."""
