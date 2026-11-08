"""Консольный интерфейс ValutaTrade Hub."""

import argparse
import shlex

from prettytable import PrettyTable

from valutatrade_hub.cli import constants as command_names
from valutatrade_hub.core.currencies import CRYPTO_CURRENCIES, FIAT_CURRENCIES
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    StaleRateError,
    StorageError,
)


class CommandParser(argparse.ArgumentParser):
    """Сообщает об ошибках ввода без завершения приложения."""

    def error(self, message):
        """Преобразует ошибку аргументов в исключение."""
        raise ValueError(message)


def build_parser():
    """Создаёт правила разбора команд приложения."""
    parser = CommandParser(prog="", description="Команды ValutaTrade Hub")
    commands = parser.add_subparsers(dest="command", required=True)

    for name in (command_names.CMD_REGISTER, command_names.CMD_LOGIN):
        command = commands.add_parser(name)
        command.add_argument("--username", required=True)
        command.add_argument("--password", required=True)

    commands.add_parser(command_names.CMD_LOGOUT)
    commands.add_parser(command_names.CMD_EXIT)
    commands.add_parser(command_names.CMD_HELP)

    portfolio = commands.add_parser(command_names.CMD_SHOW_PORTFOLIO)
    portfolio.add_argument("--base", default=None)

    for name in (command_names.CMD_BUY, command_names.CMD_SELL):
        command = commands.add_parser(name)
        command.add_argument("--currency", required=True)
        command.add_argument("--amount", type=float, required=True)

    rate = commands.add_parser(command_names.CMD_GET_RATE)
    rate.add_argument("--from", dest="from_currency", required=True)
    rate.add_argument("--to", dest="to_currency", required=True)

    update = commands.add_parser(command_names.CMD_UPDATE_RATES)
    update.add_argument(
        "--source",
        choices=("coingecko", "exchangerate"),
        default=None,
    )

    rates = commands.add_parser(command_names.CMD_SHOW_RATES)
    rates.add_argument("--currency", default=None)
    rates.add_argument("--top", type=int, default=None)

    return parser


class CLI:
    """Обрабатывает команды и хранит текущую сессию в памяти."""

    def __init__(self, service, updater):
        """Принимает сервисы и создаёт парсер команд."""
        self._service = service
        self._updater = updater
        self._parser = build_parser()
        self.current_user = None

    def run(self):
        """Читает команды до выхода пользователя."""
        print("ValutaTrade Hub")
        print("Введите help для просмотра команд.")

        while True:
            try:
                command = input("valuta> ").strip()

                if not command:
                    continue

                args = self._parser.parse_args(shlex.split(command))

                if self._execute(args):
                    break
            except CurrencyNotFoundError as error:
                print(f"Ошибка: {error}")
                supported = sorted(set(FIAT_CURRENCIES) | set(CRYPTO_CURRENCIES))
                print(f"Поддерживаемые валюты: {', '.join(supported)}")
            except ApiRequestError as error:
                print(f"Ошибка: {error}")
                print(
                    "Проверьте подключение, ключ API и наличие курсов. "
                    "Попробуйте update-rates или повторите запрос позже."
                )
            except (
                ValueError,
                ApiRequestError,
                AuthenticationError,
                CurrencyNotFoundError,
                InsufficientFundsError,
                StaleRateError,
                StorageError,
            ) as error:
                print(f"Ошибка: {error}")
            except SystemExit as error:
                if error.code:
                    print("Не удалось разобрать команду.")
            except (EOFError, KeyboardInterrupt):
                print("\nДо свидания!")
                break

    def _execute(self, args):
        """Выполняет команду; возвращает True для выхода."""
        if args.command == command_names.CMD_EXIT:
            print("До свидания!")
            return True

        if args.command == command_names.CMD_HELP:
            print("Доступные команды:")
            print("register --username <имя> --password <пароль>")
            print("login --username <имя> --password <пароль>")
            print("logout — выйти из аккаунта")
            print("show-portfolio [--base USD]")
            print("buy --currency BTC --amount 0.01")
            print("sell --currency BTC --amount 0.01")
            print("get-rate --from USD --to BTC")
            print("help — показать справку")
            print("exit — закрыть приложение")
            print("Подробности команды: <команда> --help")
            print("update-rates [--source coingecko|exchangerate]")
            print("show-rates [--currency BTC] [--top 2]")

        elif args.command == command_names.CMD_REGISTER:
            user = self._service.register(args.username, args.password)
            print(f"Пользователь '{user.username}' зарегистрирован, ID={user.user_id}.")

        elif args.command == command_names.CMD_LOGIN:
            user = self._service.login(args.username, args.password)
            self.current_user = user
            print(f"Вы вошли как '{user.username}'.")

        elif args.command == command_names.CMD_LOGOUT:
            self.current_user = None
            print("Вы вышли из аккаунта.")

        elif args.command in (command_names.CMD_BUY, command_names.CMD_SELL):
            user = self._require_user()

            if args.command == command_names.CMD_BUY:
                result = self._service.buy(user.user_id, args.currency, args.amount)
                action = "Покупка"
            else:
                result = self._service.sell(user.user_id, args.currency, args.amount)
                action = "Продажа"

            print(
                f"{action}: {result['amount']:.10g} {result['currency']}. "
                f"Баланс: {result['after']:.10g}."
            )
            print(f"Справочная стоимость: {result['estimated_usd']:.2f} USD.")

        elif args.command == command_names.CMD_GET_RATE:
            info = self._service.get_rate_info(args.from_currency, args.to_currency)
            updated_at = info["updated_at"] or "внешний курс не требуется"

            print(
                f"Курс {info['from']}→{info['to']}: {info['rate']:.10g} "
                f"(обновлено: {updated_at})"
            )
            print(
                f"Обратный курс {info['to']}→{info['from']}: "
                f"{info['inverse_rate']:.10g}"
            )

        elif args.command == command_names.CMD_SHOW_PORTFOLIO:
            user = self._require_user()
            summary = self._service.show_portfolio(user.user_id, args.base)
            self._print_portfolio(summary)

        elif args.command == command_names.CMD_UPDATE_RATES:
            result = self._updater.run_update(args.source)
            print(f"Обновлено валютных пар: {result['updated']}.")

            for error in result["errors"]:
                print(f"Предупреждение: {error}")

        elif args.command == command_names.CMD_SHOW_RATES:
            rows = self._service.show_rates(args.currency, args.top)

            if not rows:
                print("Подходящих курсов нет. Выполните update-rates.")
            else:
                table = PrettyTable()
                table.field_names = ["Пара", "Курс", "Обновлён (UTC)", "Источник"]

                for row in rows:
                    table.add_row(
                        [
                            row["pair"],
                            f"{row['rate']:.10g}",
                            row["updated_at"],
                            row["source"],
                        ]
                    )

                print(table)

        else:
            print("Обработчик этой команды ещё не подключён.")

        return False

    def _require_user(self):
        """Возвращает пользователя или требует выполнить вход."""
        if self.current_user is None:
            raise AuthenticationError("Сначала выполните login.")

        return self.current_user

    def _print_portfolio(self, summary):
        """Выводит позиции портфеля и общую стоимость."""
        base = summary["base_currency"]
        print(f"Портфель пользователя '{summary['user'].username}'")
        print(f"Базовая валюта: {base}")

        if not summary["wallets"]:
            print("Портфель пуст.")
            return

        table = PrettyTable()
        table.field_names = ["Валюта", "Баланс", f"Стоимость в {base}"]

        for row in summary["wallets"]:
            table.add_row(
                [
                    row["currency"],
                    f"{row['balance']:.10g}",
                    f"{row['value']:.2f}",
                ]
            )

        print(table)
        print(f"Итого: {summary['total']:.2f} {base}")
