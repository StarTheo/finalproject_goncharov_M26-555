"""Автоматические проверки моделей приложения."""

import unittest

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.models import Portfolio, User, Wallet


class WalletTests(unittest.TestCase):
    """Проверки баланса и операций кошелька."""

    def test_decimal_operations(self):
        """Списание десятичных сумм не оставляет ложный остаток."""
        wallet = Wallet("USD", 0.3)
        wallet.withdraw(0.1)
        wallet.withdraw(0.2)
        self.assertEqual(wallet.balance, 0.0)

    def test_oversell_preserves_balance(self):
        """Нехватка средств не меняет баланс."""
        wallet = Wallet("USD", 100)

        with self.assertRaises(InsufficientFundsError):
            wallet.withdraw(101)

        self.assertEqual(wallet.balance, 100.0)

    def test_invalid_balances(self):
        """Кошелёк отклоняет неправильные начальные значения."""
        for value in (-1, True, "100", float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Wallet("USD", value)


class UserTests(unittest.TestCase):
    """Проверки пароля и восстановления пользователя."""

    def test_invalid_password_change_preserves_old_password(self):
        """Неудачная смена сохраняет прежний пароль."""
        user = User(1, "Ivan", "1234")

        with self.assertRaises(ValueError):
            user.change_password("12")

        self.assertTrue(user.verify_password("1234"))

    def test_restore_preserves_credentials(self):
        """После восстановления работает прежний пароль."""
        original = User(1, "Ivan", "1234")
        restored = User.from_dict(original.to_dict())

        self.assertEqual(restored.get_user_info(), original.get_user_info())
        self.assertTrue(restored.verify_password("1234"))
        self.assertFalse(restored.verify_password("wrong"))
        self.assertIsNot(restored, original)


class PortfolioTests(unittest.TestCase):
    """Проверки добавления и восстановления кошельков."""

    def test_currency_normalization_preserves_wallet(self):
        """Повторное добавление валюты сохраняет кошелёк и баланс."""
        portfolio = Portfolio(1)
        wallet = portfolio.add_currency(" usd ")
        wallet.deposit(100)

        self.assertIs(portfolio.add_currency("USD"), wallet)
        self.assertEqual(list(portfolio.wallets), ["USD"])
        self.assertEqual(wallet.balance, 100.0)

    def test_restore_creates_independent_wallet(self):
        """Изменение восстановленного кошелька не меняет оригинал."""
        original = Portfolio(1)
        original.add_currency("USD").deposit(100)
        restored = Portfolio.from_dict(original.to_dict())

        restored.get_wallet("USD").withdraw(25)

        self.assertEqual(original.get_wallet("USD").balance, 100.0)
        self.assertEqual(restored.get_wallet("USD").balance, 75.0)

    def test_empty_portfolio_requires_no_rates(self):
        """Пустой портфель оценивается в ноль без курсов."""
        portfolio = Portfolio(1)

        self.assertEqual(portfolio.get_total_value("EUR"), 0.0)

        portfolio.add_currency("BTC")
        self.assertEqual(portfolio.get_total_value("EUR"), 0.0)

    def test_base_currency_wallet_requires_no_conversion(self):
        """Для кошелька в базовой валюте внешние курсы не нужны."""
        portfolio = Portfolio(1)
        portfolio.add_currency("EUR").deposit(100)

        self.assertEqual(portfolio.get_total_value("EUR"), 100.0)
