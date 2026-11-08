"""Классы валют и получение валюты по коду."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

MIN_CURRENCY_CODE_LENGTH = 2
MAX_CURRENCY_CODE_LENGTH = 5


class Currency(ABC):
    """Абстрактная валюта с названием и кодом."""

    def __init__(self, name, code):
        """Проверяет и сохраняет общие свойства валюты."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты должно быть непустой строкой.")

        if not isinstance(code, str):
            raise ValueError("Код валюты должен быть строкой.")

        if not MIN_CURRENCY_CODE_LENGTH <= len(code) <= MAX_CURRENCY_CODE_LENGTH:
            raise ValueError("Код валюты должен содержать от 2 до 5 символов.")

        if not code.isascii() or not code.isalpha() or not code.isupper():
            raise ValueError("Код валюты должен состоять из заглавных латинских букв.")

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self):
        """Возвращает описание конкретного вида валюты."""
        raise NotImplementedError


class FiatCurrency(Currency):
    """Фиатная валюта со страной или регионом выпуска."""

    def __init__(self, name, code, issuing_country):
        """Создаёт фиатную валюту."""
        super().__init__(name, code)

        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна или регион выпуска должны быть указаны.")

        self.issuing_country = issuing_country

    def get_display_info(self):
        """Возвращает описание фиатной валюты."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и рыночной капитализацией."""

    def __init__(self, name, code, algorithm, market_cap):
        """Создаёт криптовалюту с проверенными характеристиками."""
        super().__init__(name, code)

        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм должен быть непустой строкой.")

        if type(market_cap) not in (int, float):
            raise ValueError("Капитализация должна быть числом.")

        if not 0 <= market_cap < float("inf"):
            raise ValueError("Капитализация должна быть конечной и неотрицательной.")

        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self):
        """Возвращает описание криптовалюты."""
        market_cap_text = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {market_cap_text})"
        )


FIAT_CURRENCIES = {
    "USD": ("US Dollar", "United States"),
    "EUR": ("Euro", "Eurozone"),
    "GBP": ("Pound Sterling", "United Kingdom"),
    "RUB": ("Russian Ruble", "Russia"),
}

CRYPTO_CURRENCIES = {
    "BTC": ("Bitcoin", "SHA-256", 1.12e12),
    "ETH": ("Ethereum", "Proof of Stake", 4.5e11),
    "SOL": ("Solana", "Proof of History / Proof of Stake", 7e10),
}


def get_currency(code):
    """Создаёт объект поддерживаемой валюты по её коду."""
    if not isinstance(code, str):
        raise ValueError("Код валюты должен быть строкой.")

    normalized_code = code.strip().upper()

    if normalized_code in FIAT_CURRENCIES:
        name, country = FIAT_CURRENCIES[normalized_code]
        return FiatCurrency(name, normalized_code, country)

    if normalized_code in CRYPTO_CURRENCIES:
        name, algorithm, market_cap = CRYPTO_CURRENCIES[normalized_code]
        return CryptoCurrency(name, normalized_code, algorithm, market_cap)

    raise CurrencyNotFoundError(f"Неизвестная валюта '{normalized_code}'")
