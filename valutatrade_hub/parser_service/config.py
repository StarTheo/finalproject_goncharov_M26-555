"""Конфигурация сервиса получения курсов валют."""

import os

from valutatrade_hub.core.utils import BASE_CURRENCY
from valutatrade_hub.infra.settings import SettingsLoader

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
EXCHANGERATE_URL = "https://v6.exchangerate-api.com/v6"

FIAT_CODES = ("EUR", "GBP", "RUB")

CRYPTO_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

EXCHANGERATE_KEY_ENV = "EXCHANGERATE_API_KEY"
COINGECKO_KEY_ENV = "COINGECKO_API_KEY"


class ParserConfig:
    """Объединяет настройки источников курсов и приложения."""

    def __init__(self, settings=None):
        """Получает настройки приложения и ключи из окружения."""
        if settings is None:
            settings = SettingsLoader()

        self.request_timeout = settings.get("request_timeout")
        self.update_interval = settings.get("update_interval_seconds")

        self.coingecko_url = COINGECKO_URL
        self.exchangerate_url = EXCHANGERATE_URL

        self.fiat_codes = FIAT_CODES
        self.crypto_id_map = CRYPTO_ID_MAP.copy()

        self.exchangerate_api_key = os.getenv(EXCHANGERATE_KEY_ENV)
        self.coingecko_api_key = os.getenv(COINGECKO_KEY_ENV)
        self.base_currency = BASE_CURRENCY
