"""Сценарии регистрации, входа и работы с валютным портфелем."""

from datetime import datetime, timezone

from valutatrade_hub.core.currencies import CRYPTO_CURRENCIES, get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    InsufficientFundsError,
    StaleRateError,
    StorageError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import BASE_CURRENCY, validate_amount
from valutatrade_hub.decorators import create_cacher, log_action
from valutatrade_hub.infra.settings import SettingsLoader

FIRST_USER_ID = 1


class TradingService:
    """Выполняет сценарии приложения через переданное хранилище."""

    def __init__(self, database, settings=None):
        """Сохраняет хранилище и настройки приложения."""
        self._database = database
        self._settings = SettingsLoader() if settings is None else settings
        self._rate_cache = create_cacher(self._settings.get("rates_ttl_seconds"))

    def register(self, username, password):
        """Регистрирует пользователя и создаёт пустой портфель."""
        users = self._database.read("users")

        for user_data in users:
            if user_data["username"] == username:
                raise ValueError(f"Имя пользователя '{username}' уже занято.")

        next_id = (
            max(
                (user_data["user_id"] for user_data in users),
                default=FIRST_USER_ID - 1,
            )
            + 1
        )

        user = User(next_id, username, password)
        portfolio = Portfolio(user.user_id, user)

        portfolios = self._database.read("portfolios")
        users.append(user.to_dict())
        portfolios.append(portfolio.to_dict())

        self._database.write("users", users)
        self._database.write("portfolios", portfolios)

        return user

    def login(self, username, password):
        """Проверяет учётные данные и возвращает пользователя."""
        users = self._database.read("users")

        for user_data in users:
            if user_data["username"] == username:
                user = User.from_dict(user_data)

                if user.verify_password(password):
                    return user

                break

        raise AuthenticationError("Неверное имя пользователя или пароль.")

    def get_user(self, user_id):
        """Возвращает пользователя по идентификатору."""
        users = self._database.read("users")

        for user_data in users:
            if user_data["user_id"] == user_id:
                return User.from_dict(user_data)

        raise AuthenticationError("Пользователь не найден.")

    def get_portfolio(self, user_id):
        """Загружает портфель и передаёт ему объект владельца."""
        user = self.get_user(user_id)
        portfolios = self._database.read("portfolios")

        for portfolio_data in portfolios:
            if portfolio_data["user_id"] == user_id:
                return Portfolio.from_dict(portfolio_data, user)

        raise StorageError(f"Портфель пользователя ID={user_id} не найден.")

    def _save_portfolio(self, portfolio):
        """Заменяет сохранённые данные существующего портфеля."""
        portfolios = self._database.read("portfolios")
        updated_data = portfolio.to_dict()

        for index, portfolio_data in enumerate(portfolios):
            if portfolio_data["user_id"] == updated_data["user_id"]:
                portfolios[index] = updated_data
                self._database.write("portfolios", portfolios)
                return

        raise StorageError("Не удалось найти портфель для сохранения.")

    def get_rate(self, from_currency, to_currency):
        """Возвращает числовое значение свежего курса."""
        return self.get_rate_info(from_currency, to_currency)["rate"]

    def get_rate_info(self, from_currency, to_currency):
        """Возвращает курс, обратный курс и время используемых данных."""
        from_code = get_currency(from_currency).code
        to_code = get_currency(to_currency).code

        if from_code == to_code:
            return {
                "from": from_code,
                "to": to_code,
                "rate": 1.0,
                "inverse_rate": 1.0,
                "updated_at": None,
            }

        snapshot = self._database.read("rates")
        now = datetime.now(timezone.utc)
        from_usd = self._get_usd_rate(from_code, snapshot, now)
        to_usd = self._get_usd_rate(to_code, snapshot, now)

        cache_key = (from_code, to_code, from_usd, to_usd)
        rate = self._rate_cache(cache_key, lambda: from_usd / to_usd)

        if not 0 < rate < float("inf"):
            raise ApiRequestError("Невозможно вычислить корректный курс.")

        inverse_rate = 1 / rate

        if not 0 < inverse_rate < float("inf"):
            raise ApiRequestError("Невозможно вычислить обратный курс.")

        timestamps = []

        for code in (from_code, to_code):
            if code != BASE_CURRENCY:
                value = snapshot["pairs"][f"{code}_{BASE_CURRENCY}"]["updated_at"]
                timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))

        return {
            "from": from_code,
            "to": to_code,
            "rate": rate,
            "inverse_rate": inverse_rate,
            "updated_at": min(timestamps).isoformat(),
        }

    def _get_usd_rate(self, code, snapshot, now):
        """Читает курс валюты к USD и проверяет его свежесть."""
        if code == BASE_CURRENCY:
            return 1.0

        pair = f"{code}_{BASE_CURRENCY}"
        entry = snapshot["pairs"].get(pair)

        if entry is None:
            raise ApiRequestError(f"Курс {pair} отсутствует. Выполните update-rates.")

        rate = entry.get("rate")

        if type(rate) not in (int, float) or not 0 < rate < float("inf"):
            raise ApiRequestError(f"Сохранён некорректный курс {pair}.")

        try:
            updated_at = datetime.fromisoformat(
                entry["updated_at"].replace("Z", "+00:00")
            )

            if updated_at.tzinfo is None:
                raise ValueError("Отсутствует часовой пояс.")

            age = (now - updated_at).total_seconds()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StaleRateError(
                f"Некорректное время курса {pair}. Выполните update-rates."
            ) from None

        if age < 0 or age > self._settings.get("rates_ttl_seconds"):
            raise StaleRateError(
                f"Курс {pair} устарел или имеет дату в будущем. Выполните update-rates."
            )

        return float(rate)

    @log_action("BUY", verbose=True)
    def buy(self, user_id, currency_code, amount):
        """Увеличивает баланс валюты и возвращает сведения о покупке."""
        code = get_currency(currency_code).code
        amount = validate_amount(amount)
        portfolio = self.get_portfolio(user_id)
        rate = self.get_rate(code, BASE_CURRENCY)

        wallet = portfolio.add_currency(code)
        before = wallet.balance
        wallet.deposit(amount)

        self._save_portfolio(portfolio)

        return {
            "currency": code,
            "amount": amount,
            "rate": rate,
            "estimated_usd": amount * rate,
            "before": before,
            "after": wallet.balance,
        }

    @log_action("SELL", verbose=True)
    def sell(self, user_id, currency_code, amount):
        """Уменьшает баланс валюты и возвращает сведения о продаже."""
        code = get_currency(currency_code).code
        amount = validate_amount(amount)
        portfolio = self.get_portfolio(user_id)
        rate = self.get_rate(code, BASE_CURRENCY)

        wallet = portfolio.get_wallet(code)

        if wallet is None:
            raise InsufficientFundsError(
                f"Недостаточно средств: кошелёк {code} отсутствует."
            )

        before = wallet.balance
        wallet.withdraw(amount)

        self._save_portfolio(portfolio)

        return {
            "currency": code,
            "amount": amount,
            "rate": rate,
            "estimated_usd": amount * rate,
            "before": before,
            "after": wallet.balance,
        }

    def show_portfolio(self, user_id, base_currency=None):
        """Возвращает портфель и его оценку по свежим курсам."""
        if base_currency is None:
            base_currency = self._settings.get("default_base_currency")

        base_code = get_currency(base_currency).code
        portfolio = self.get_portfolio(user_id)
        rates = {}
        rows = []

        for code, wallet in portfolio.wallets.items():
            if wallet.balance == 0:
                continue

            conversion_rate = self.get_rate(code, base_code)
            value = wallet.balance * conversion_rate

            rows.append(
                {
                    "currency": code,
                    "balance": wallet.balance,
                    "value": value,
                }
            )

            if code != base_code and code != BASE_CURRENCY:
                rates[f"{code}_{BASE_CURRENCY}"] = self.get_rate(code, BASE_CURRENCY)

        if rows and base_code != BASE_CURRENCY:
            rates[f"{base_code}_{BASE_CURRENCY}"] = self.get_rate(
                base_code, BASE_CURRENCY
            )

        total = portfolio.get_total_value(base_code, rates) if rows else 0.0

        return {
            "user": portfolio.user,
            "base_currency": base_code,
            "wallets": rows,
            "total": total,
        }

    def show_rates(self, currency=None, top=None):
        """Возвращает сохранённые курсы с фильтрацией."""
        if top is not None and (type(top) is not int or top <= 0):
            raise ValueError("Параметр top должен быть положительным целым числом.")

        code_filter = None if currency is None else get_currency(currency).code
        snapshot = self._database.read("rates")
        rows = []

        for pair, entry in snapshot["pairs"].items():
            code, quote = pair.split("_")

            if quote != BASE_CURRENCY:
                continue

            if code_filter is not None and code != code_filter:
                continue

            if top is not None and code not in CRYPTO_CURRENCIES:
                continue

            rows.append(
                {
                    "pair": pair,
                    "rate": entry["rate"],
                    "updated_at": entry["updated_at"],
                    "source": entry["source"],
                }
            )

        rows.sort(key=lambda row: row["rate"], reverse=True)

        if top is not None:
            rows = rows[:top]

        return rows
