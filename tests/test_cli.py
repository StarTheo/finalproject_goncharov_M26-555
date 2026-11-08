"""Проверки команд консольного интерфейса."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from valutatrade_hub.cli.interface import CLI
from valutatrade_hub.core.exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
)


class CLITests(unittest.TestCase):
    """Проверяет поведение интерфейса без сети и файлов."""

    def run_commands(self, service, commands):
        """Выполняет последовательность команд и возвращает вывод."""
        cli = CLI(service, Mock())
        output = StringIO()

        with (
            patch("builtins.input", side_effect=commands),
            redirect_stdout(output),
        ):
            cli.run()

        return cli, output.getvalue()

    def test_trade_requires_login(self):
        """Без входа торговый сервис не вызывается."""
        service = Mock()
        _, output = self.run_commands(
            service,
            ["buy --currency USD --amount 1", "exit"],
        )

        self.assertIn("Сначала выполните login.", output)
        service.buy.assert_not_called()

    def test_unknown_currency_shows_supported_codes(self):
        """Ошибка валюты сопровождается подсказкой."""
        service = Mock()
        service.get_rate_info.side_effect = CurrencyNotFoundError(
            "Неизвестная валюта 'XYZ'"
        )
        _, output = self.run_commands(
            service,
            ["get-rate --from XYZ --to USD", "exit"],
        )

        self.assertIn("Поддерживаемые валюты:", output)
        self.assertIn("BTC", output)
        self.assertIn("USD", output)

    def test_failed_login_preserves_session(self):
        """Неудачный повторный вход сохраняет прежнего пользователя."""
        service = Mock()
        user = Mock()
        user.username = "Ivan"
        user.user_id = 1
        service.login.side_effect = [
            user,
            AuthenticationError("Неверное имя пользователя или пароль."),
        ]

        cli, output = self.run_commands(
            service,
            [
                "login --username Ivan --password 1234",
                "login --username Ivan --password wrong",
                "exit",
            ],
        )

        self.assertIs(cli.current_user, user)
        self.assertIn("Неверное имя пользователя или пароль.", output)

    def test_help_and_invalid_command_do_not_exit(self):
        """После справки и ошибки приложение принимает следующую команду."""
        _, output = self.run_commands(
            Mock(),
            ["buy --help", "unknown-command", "help", "exit"],
        )

        self.assertIn("--currency", output)
        self.assertIn("Ошибка:", output)
        self.assertIn("Доступные команды:", output)
        self.assertIn("До свидания!", output)
