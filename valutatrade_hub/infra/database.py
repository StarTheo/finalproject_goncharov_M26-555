"""Хранение данных приложения в JSON-файлах."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.infra.settings import SettingsLoader

DATA_FILES = {
    "users": "users.json",
    "portfolios": "portfolios.json",
    "rates": "rates.json",
    "exchange_rates": "exchange_rates.json",
}


class DatabaseManager:
    """Предоставляет единый объект для работы с хранилищем."""

    _instance = None

    def __new__(cls):
        """Создаёт экземпляр только при первом обращении."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        """Определяет папку данных и создаёт её при необходимости."""
        if getattr(self, "_initialized", False):
            return

        settings = SettingsLoader()
        self._data_dir = Path(settings.get("data_dir"))
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    def read(self, name):
        """Читает хранилище или возвращает начальные данные."""
        if name not in DATA_FILES:
            raise ValueError(f"Неизвестное хранилище: {name}.")

        path = self._data_dir / DATA_FILES[name]

        if not path.exists():
            if name == "rates":
                return {"pairs": {}, "last_refresh": None}

            return []

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError) as error:
            raise StorageError(f"Не удалось прочитать файл '{path.name}'.") from error

        self._validate_data(name, data)
        return data

    def write(self, name, data):
        """Сохраняет данные через временный файл и замену основного."""
        if name not in DATA_FILES:
            raise ValueError(f"Неизвестное хранилище: {name}.")

        self._validate_data(name, data)

        path = self._data_dir / DATA_FILES[name]
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._data_dir,
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, path)
        except (OSError, TypeError, ValueError) as error:
            raise StorageError(f"Не удалось сохранить файл '{path.name}'.") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _validate_timestamp(value):
        """Проверяет строку времени с указанным часовым поясом."""
        if not isinstance(value, str):
            raise ValueError("Дата должна быть строкой.")

        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            raise ValueError("В дате отсутствует часовой пояс.")

    def _validate_data(self, name, data):
        """Проверяет структуру данных перед чтением или записью."""
        try:
            if name != "rates":
                if not isinstance(data, list):
                    raise ValueError("Ожидался список.")

                if not all(isinstance(record, dict) for record in data):
                    raise ValueError("Записи должны быть словарями.")

                self._validate_records(name, data)
                return

            if not isinstance(data, dict):
                raise ValueError("Ожидался словарь.")

            pairs = data["pairs"]
            last_refresh = data["last_refresh"]

            if not isinstance(pairs, dict):
                raise ValueError("Поле pairs должно быть словарём.")

            if last_refresh is not None:
                self._validate_timestamp(last_refresh)
            elif pairs:
                raise ValueError("Для непустого снимка нужна дата обновления.")

            for pair, entry in pairs.items():
                if not isinstance(pair, str):
                    raise ValueError("Имя пары должно быть строкой.")

                codes = pair.split("_")

                if len(codes) != 2 or not all(
                    code.isascii() and code.isalpha() and code.isupper()
                    for code in codes
                ):
                    raise ValueError("Некорректное имя валютной пары.")

                if not isinstance(entry, dict):
                    raise ValueError("Описание курса должно быть словарём.")

                rate = entry["rate"]

                if type(rate) not in (int, float) or not 0 < rate < float("inf"):
                    raise ValueError("Курс должен быть конечным положительным числом.")

                self._validate_timestamp(entry["updated_at"])

                source = entry["source"]

                if not isinstance(source, str) or not source.strip():
                    raise ValueError("Не указан источник курса.")
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise StorageError(
                f"Неверная структура хранилища '{name}': {error}"
            ) from error

    def _validate_records(self, name, records):
        """Проверяет обязательные поля записей хранилища."""
        for record in records:
            if name in ("users", "portfolios"):
                user_id = record["user_id"]

                if type(user_id) is not int or user_id <= 0:
                    raise ValueError(
                        "Идентификатор пользователя должен быть положительным."
                    )

            if name == "users":
                for field in ("username", "hashed_password", "salt"):
                    value = record[field]

                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"Поле '{field}' должно быть непустой строкой."
                        )

                self._validate_timestamp(record["registration_date"])

            elif name == "portfolios":
                wallets = record["wallets"]

                if not isinstance(wallets, dict):
                    raise ValueError("Поле wallets должно быть словарём.")

                for code, wallet in wallets.items():
                    if (
                        not isinstance(code, str)
                        or not 2 <= len(code) <= 5
                        or not code.isascii()
                        or not code.isalpha()
                        or not code.isupper()
                    ):
                        raise ValueError("Некорректный код валюты кошелька.")

                    if not isinstance(wallet, dict):
                        raise ValueError("Кошелёк должен быть словарём.")

                    balance = wallet["balance"]

                    if type(balance) not in (int, float) or not 0 <= balance < float(
                        "inf"
                    ):
                        raise ValueError("Некорректный баланс кошелька.")

            elif name == "exchange_rates":
                for field in ("id", "pair", "source"):
                    value = record[field]

                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"Поле '{field}' должно быть непустой строкой."
                        )

                rate = record["rate"]

                if type(rate) not in (int, float) or not 0 < rate < float("inf"):
                    raise ValueError("Некорректный курс в истории.")

                self._validate_timestamp(record["timestamp"])
