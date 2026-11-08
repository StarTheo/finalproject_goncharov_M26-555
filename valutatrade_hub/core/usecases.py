"""Сценарии регистрации, входа и работы с валютным портфелем."""

from valutatrade_hub.core.exceptions import AuthenticationError, StorageError
from valutatrade_hub.core.models import Portfolio, User

FIRST_USER_ID = 1


class TradingService:
    """Выполняет сценарии приложения через переданное хранилище."""

    def __init__(self, database):
        """Сохраняет объект хранилища для выполнения операций."""
        self._database = database

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
