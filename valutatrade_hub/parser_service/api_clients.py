"""Клиенты внешних источников курсов валют."""

from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError


class BaseApiClient(ABC):
    """Задаёт общий интерфейс источников и обработку HTTP-запросов."""

    def __init__(self, config):
        """Сохраняет конфигурацию клиента."""
        self.config = config

    def _get_json(self, url, params=None, headers=None):
        """Выполняет HTTP-запрос и возвращает JSON-объект."""
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.config.request_timeout,
            )
        except requests.Timeout:
            raise ApiRequestError("Источник курсов не ответил вовремя.") from None
        except requests.RequestException:
            raise ApiRequestError(
                "Не удалось подключиться к источнику курсов."
            ) from None

        if response.status_code in (401, 403):
            raise ApiRequestError("Источник отклонил доступ. Проверьте ключ API.")

        if response.status_code == 429:
            raise ApiRequestError("Превышен лимит запросов к источнику курсов.")

        if not 200 <= response.status_code < 300:
            raise ApiRequestError(
                f"Источник курсов вернул HTTP {response.status_code}."
            )

        try:
            data = response.json()
        except ValueError:
            raise ApiRequestError("Источник вернул некорректный JSON.") from None

        if not isinstance(data, dict):
            raise ApiRequestError("Источник вернул неожиданную структуру ответа.")

        return data

    @abstractmethod
    def fetch_rates(self):
        """Возвращает словарь курсов валют к USD."""
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    """Получает курсы криптовалют к USD через CoinGecko."""

    source = "CoinGecko"

    def fetch_rates(self):
        """Запрашивает и проверяет цены настроенных криптовалют."""
        params = {
            "ids": ",".join(self.config.crypto_id_map.values()),
            "vs_currencies": "usd",
            "precision": "full",
        }

        headers = {}

        if self.config.coingecko_api_key:
            headers["x-cg-demo-api-key"] = self.config.coingecko_api_key

        data = self._get_json(
            self.config.coingecko_url,
            params=params,
            headers=headers,
        )

        rates = {}

        for code, coin_id in self.config.crypto_id_map.items():
            coin_data = data.get(coin_id)

            if not isinstance(coin_data, dict):
                raise ApiRequestError(f"CoinGecko не вернул данные для {code}.")

            rate = coin_data.get("usd")

            if type(rate) not in (int, float):
                raise ApiRequestError(f"CoinGecko вернул некорректный курс {code}.")

            if not 0 < rate < float("inf"):
                raise ApiRequestError(f"CoinGecko вернул недопустимый курс {code}.")

            rates[f"{code}_USD"] = float(rate)

        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Получает курсы фиатных валют к USD."""

    source = "ExchangeRate-API"

    def fetch_rates(self):
        """Запрашивает курсы от USD и вычисляет обратные значения."""
        if not self.config.exchangerate_api_key:
            raise ApiRequestError(
                "Не задан ключ ExchangeRate-API: EXCHANGERATE_API_KEY."
            )

        url = (
            f"{self.config.exchangerate_url}/"
            f"{self.config.exchangerate_api_key}/latest/USD"
        )
        data = self._get_json(url)

        if data.get("result") != "success":
            raise ApiRequestError("ExchangeRate-API сообщил об ошибке запроса.")

        if data.get("base_code") != "USD":
            raise ApiRequestError("ExchangeRate-API вернул неожиданную базовую валюту.")

        conversion_rates = data.get("conversion_rates")

        if not isinstance(conversion_rates, dict):
            raise ApiRequestError("В ответе отсутствует словарь conversion_rates.")

        rates = {}

        for code in self.config.fiat_codes:
            value = conversion_rates.get(code)

            if type(value) not in (int, float):
                raise ApiRequestError(f"Не получен числовой курс для {code}.")

            if not 0 < value < float("inf"):
                raise ApiRequestError(f"Получен недопустимый курс для {code}.")

            inverse_rate = 1 / value

            if not 0 < inverse_rate < float("inf"):
                raise ApiRequestError(f"Невозможно вычислить обратный курс {code}.")

            rates[f"{code}_USD"] = inverse_rate

        return rates
