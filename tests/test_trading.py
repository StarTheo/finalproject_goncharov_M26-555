"""Проверки торговых сценариев и сохранности данных."""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from valutatrade_hub.core.exceptions import (
    AuthenticationError,
    InsufficientFundsError,
    StaleRateError,
    StorageError,
)
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.infra.database import DatabaseManager


class TradingTests(unittest.TestCase):
    """Проверяет сценарии на изолированном хранилище."""

    def setUp(self):
        """Создаёт временное хранилище, пользователя и свежие курсы."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.db = DatabaseManager()
        directory_patch = patch.object(self.db, "_data_dir", Path(directory.name))
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

        self.service = TradingService(self.db)
        self.user = self.service.register("Trader", "1234")
        timestamp = datetime.now(timezone.utc).isoformat()

        self.db.write(
            "rates",
            {
                "pairs": {
                    "BTC_USD": {
                        "rate": 60000.0,
                        "updated_at": timestamp,
                        "source": "Test",
                    },
                    "EUR_USD": {
                        "rate": 1.25,
                        "updated_at": timestamp,
                        "source": "Test",
                    },
                },
                "last_refresh": timestamp,
            },
        )

    def test_login(self):
        """Вход проверяет пароль сохранённого пользователя."""
        user = self.service.login("Trader", "1234")
        self.assertEqual(user.user_id, self.user.user_id)

        with self.assertRaises(AuthenticationError):
            self.service.login("Trader", "wrong")

    def test_buy_sell_and_valuation(self):
        """Торговля сохраняет баланс и позволяет оценить портфель."""
        self.service.buy(self.user.user_id, "BTC", 0.1)
        self.service.sell(self.user.user_id, "BTC", 0.04)

        portfolio = self.service.get_portfolio(self.user.user_id)
        self.assertEqual(portfolio.get_wallet("BTC").balance, 0.06)
        self.assertIsNone(portfolio.get_wallet("USD"))

        summary = self.service.show_portfolio(self.user.user_id, "EUR")
        self.assertAlmostEqual(summary["total"], 2880.0)

    def test_oversell_does_not_change_file(self):
        """Неудачная продажа не меняет сохранённый портфель."""
        self.service.buy(self.user.user_id, "BTC", 0.1)
        before = (self.db._data_dir / "portfolios.json").read_bytes()

        with self.assertRaises(InsufficientFundsError):
            self.service.sell(self.user.user_id, "BTC", 1)

        after = (self.db._data_dir / "portfolios.json").read_bytes()
        self.assertEqual(before, after)

    def test_stale_rate_prevents_trade(self):
        """Старая дата пары запрещает покупку даже после расчёта курса."""
        self.service.get_rate("BTC", "USD")
        snapshot = self.db.read("rates")
        snapshot["pairs"]["BTC_USD"]["updated_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        self.db.write("rates", snapshot)
        before = self.db.read("portfolios")

        with self.assertRaises(StaleRateError):
            self.service.buy(self.user.user_id, "BTC", 0.1)

        self.assertEqual(self.db.read("portfolios"), before)

    def test_invalid_json_write_preserves_file(self):
        """Ошибка сериализации не повреждает существующий файл."""
        path = self.db._data_dir / "users.json"
        before = path.read_bytes()

        with self.assertRaises(StorageError):
            self.db.write("users", [{"invalid": float("nan")}])

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.db._data_dir.glob("*.tmp")), [])
