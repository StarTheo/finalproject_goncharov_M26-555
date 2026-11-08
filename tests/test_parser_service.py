"""Проверки API-клиентов и обновления курсов без сетевых запросов."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


class ParserServiceTests(unittest.TestCase):
    """Проверяет преобразование ответов и сохранность курсов."""

    def setUp(self):
        """Создаёт клиентов и временное хранилище."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.db = DatabaseManager()
        directory_patch = patch.object(self.db, "_data_dir", Path(directory.name))
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

        config = ParserConfig()
        config.exchangerate_api_key = "test-key"
        self.crypto = CoinGeckoClient(config)
        self.fiat = ExchangeRateApiClient(config)
        self.storage = RatesStorage(self.db)
        self.updater = RatesUpdater([self.crypto, self.fiat], self.storage)

        self.storage.save(
            [
                {
                    "pair": "EUR_USD",
                    "rate": 1.25,
                    "updated_at": "2026-11-08T00:00:00+00:00",
                    "source": self.fiat.source,
                }
            ]
        )

    def test_fiat_rates_are_inverted(self):
        """Клиент преобразует USD→EUR в EUR→USD без округления."""
        response = {
            "result": "success",
            "base_code": "USD",
            "conversion_rates": {"EUR": 0.927, "GBP": 0.809, "RUB": 98.45},
        }

        with patch.object(self.fiat, "_get_json", return_value=response):
            rates = self.fiat.fetch_rates()

        self.assertEqual(rates["EUR_USD"], 1 / 0.927)
        self.assertEqual(rates["GBP_USD"], 1 / 0.809)
        self.assertEqual(rates["RUB_USD"], 1 / 98.45)

    def test_invalid_crypto_price_is_rejected(self):
        """Некорректная цена не превращается в допустимый курс."""
        for value in (None, True, "60000", 0, -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                response = {"bitcoin": {"usd": value}}

                with patch.object(self.crypto, "_get_json", return_value=response):
                    with self.assertRaises(ApiRequestError):
                        self.crypto.fetch_rates()

    def test_partial_failure_preserves_old_pair(self):
        """Успешный источник сохраняется, старая пара не изменяется."""
        old_eur = self.db.read("rates")["pairs"]["EUR_USD"]

        with (
            patch.object(self.crypto, "fetch_rates", return_value={"BTC_USD": 60000.0}),
            patch.object(
                self.fiat,
                "fetch_rates",
                side_effect=ApiRequestError("Источник недоступен."),
            ),
        ):
            result = self.updater.run_update()

        pairs = self.db.read("rates")["pairs"]
        self.assertEqual(result["updated"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(pairs["BTC_USD"]["rate"], 60000.0)
        self.assertEqual(pairs["EUR_USD"], old_eur)

    def test_total_failure_preserves_both_files(self):
        """Полный отказ не меняет снимок и историю."""
        paths = [
            self.db._data_dir / "rates.json",
            self.db._data_dir / "exchange_rates.json",
        ]
        before = [path.read_bytes() for path in paths]

        with (
            patch.object(
                self.crypto,
                "fetch_rates",
                side_effect=ApiRequestError("Источник недоступен."),
            ),
            patch.object(
                self.fiat,
                "fetch_rates",
                side_effect=ApiRequestError("Источник недоступен."),
            ),
        ):
            with self.assertRaises(ApiRequestError):
                self.updater.run_update()

        self.assertEqual([path.read_bytes() for path in paths], before)
