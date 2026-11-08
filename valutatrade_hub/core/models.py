"""Модели пользователя, кошелька и портфеля."""

import secrets
from datetime import datetime, timezone
from decimal import Decimal

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import (
    MIN_PASSWORD_LENGTH,
    PASSWORD_SALT_BYTES,
    hash_password,
)


class Wallet:
    """Кошелёк для хранения одной валюты."""

    def __init__(self, currency_code, balance=0.0):
        """Создаёт кошелёк с проверенным начальным балансом."""
        self.currency_code = get_currency(currency_code).code
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
                f"Недостаточно средств: доступно {self.balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} "
                f"{self.currency_code}"
            )

        self.balance = float(Decimal(str(self.balance)) - Decimal(str(amount)))

    def get_balance_info(self):
        """Возвращает описание текущего баланса кошелька."""
        return f"{self.currency_code}: {self.balance:.4f}"


class User:
    """Пользователь приложения."""

    def __init__(self, user_id, username, password):
        """Создаёт пользователя и хеширует его пароль."""
        self._user_id = user_id
        self.username = username
        self._salt = secrets.token_hex(PASSWORD_SALT_BYTES)
        self._hashed_password = hash_password(password, self._salt)
        self._registration_date = datetime.now(timezone.utc).isoformat()

    @property
    def user_id(self):
        """Возвращает идентификатор пользователя."""
        return self._user_id

    @property
    def username(self):
        """Возвращает имя пользователя."""
        return self._username

    @username.setter
    def username(self, value):
        """Проверяет и устанавливает имя пользователя."""
        if not isinstance(value, str):
            raise ValueError("Имя пользователя должно быть строкой.")

        if not value.strip():
            raise ValueError("Имя пользователя не должно быть пустым.")

        self._username = value

    def verify_password(self, password):
        """Возвращает результат проверки введённого пароля."""
        if not isinstance(password, str):
            return False

        if len(password) < MIN_PASSWORD_LENGTH:
            return False

        candidate_hash = hash_password(password, self._salt)
        return secrets.compare_digest(candidate_hash, self._hashed_password)

    def change_password(self, new_password):
        """Устанавливает новый пароль и генерирует новую соль."""
        new_salt = secrets.token_hex(PASSWORD_SALT_BYTES)
        new_hash = hash_password(new_password, new_salt)

        self._salt = new_salt
        self._hashed_password = new_hash

    @property
    def registration_date(self):
        """Возвращает дату регистрации."""
        return self._registration_date

    def get_user_info(self):
        """Возвращает сведения о пользователе без хеша пароля и соли."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date,
        }

    def to_dict(self):
        """Возвращает данные пользователя для сохранения."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date,
        }

    @classmethod
    def from_dict(cls, data):
        """Восстанавливает пользователя из сохранённых данных."""
        user = cls.__new__(cls)
        user._user_id = data["user_id"]
        user.username = data["username"]
        user._hashed_password = data["hashed_password"]
        user._salt = data["salt"]
        user._registration_date = data["registration_date"]
        return user


class Portfolio:
    """Портфель с кошельками одного пользователя."""

    def __init__(self, user_id, user=None):
        """Создаёт пустой портфель пользователя."""
        self._user_id = user_id
        self._user = user
        self._wallets = {}

    @property
    def user(self):
        """Возвращает переданный объект пользователя."""
        return self._user

    @property
    def wallets(self):
        """Возвращает поверхностную копию словаря кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code):
        """Добавляет кошелёк поддерживаемой валюты без дублирования."""
        code = get_currency(currency_code).code

        if code not in self._wallets:
            self._wallets[code] = Wallet(code)

        return self._wallets[code]

    def get_wallet(self, currency_code):
        """Возвращает кошелёк поддерживаемой валюты или None."""
        code = get_currency(currency_code).code
        return self._wallets.get(code)

    def to_dict(self):
        """Возвращает данные портфеля для сохранения."""
        wallets_data = {}

        for currency_code, wallet in self._wallets.items():
            wallets_data[currency_code] = {"balance": wallet.balance}

        return {
            "user_id": self._user_id,
            "wallets": wallets_data,
        }

    @classmethod
    def from_dict(cls, data, user=None):
        """Восстанавливает портфель и его кошельки из словаря."""
        portfolio = cls(data["user_id"], user)

        for currency_code, wallet_data in data["wallets"].items():
            wallet = portfolio.add_currency(currency_code)
            wallet.balance = wallet_data["balance"]

        return portfolio

    def get_total_value(self, base_currency="USD", rates=None):
        """Считает стоимость портфеля по переданным курсам к USD."""
        base_code = get_currency(base_currency).code
        rates = {} if rates is None else rates
        total = 0.0

        for code, wallet in self._wallets.items():
            if wallet.balance == 0:
                continue

            if code == base_code:
                total += wallet.balance
                continue

            base_rate = 1.0 if base_code == "USD" else rates[f"{base_code}_USD"]
            rate = 1.0 if code == "USD" else rates[f"{code}_USD"]
            total += wallet.balance * rate / base_rate

        return total
