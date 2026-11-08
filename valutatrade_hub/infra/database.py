"""Хранение данных приложения в JSON-файлах."""

import json
import os
import tempfile
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

        expected_type = dict if name == "rates" else list

        if not isinstance(data, expected_type):
            raise StorageError(f"Неверная структура файла '{path.name}'.")

        return data

    def write(self, name, data):
        """Сохраняет данные через временный файл и замену основного."""
        if name not in DATA_FILES:
            raise ValueError(f"Неизвестное хранилище: {name}.")

        expected_type = dict if name == "rates" else list

        if not isinstance(data, expected_type):
            raise StorageError("Неверный тип данных для сохранения.")

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
