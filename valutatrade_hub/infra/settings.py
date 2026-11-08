"""Настройки приложения."""

import tomllib
from pathlib import Path

from valutatrade_hub.core.currencies import get_currency

DEFAULT_SETTINGS = {
    "data_dir": "data",
    "logs_dir": "logs",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "request_timeout": 10,
    "update_interval_seconds": 300,
}


class SettingsLoader:
    """Предоставляет единый экземпляр настроек приложения."""

    _instance = None

    def __new__(cls):
        """Создаёт экземпляр только при первом обращении."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        """Загружает настройки один раз при создании экземпляра."""
        if getattr(self, "_initialized", False):
            return

        self.reload()
        self._initialized = True

    def get(self, key):
        """Возвращает значение настройки по имени."""
        return self._settings[key]

    def get_all(self):
        """Возвращает копию всех настроек."""
        return self._settings.copy()

    def reload(self, config_path="pyproject.toml"):
        """Загружает настройки из файла поверх значений по умолчанию."""
        settings = DEFAULT_SETTINGS.copy()
        path = Path(config_path)

        if path.is_file():
            with path.open("rb") as file:
                config = tomllib.load(file)

            project_settings = config.get("tool", {}).get("valutatrade", {})
            settings.update(project_settings)

        self._validate(settings)
        self._settings = settings

    def _validate(self, settings):
        """Проверяет значения настроек перед их применением."""
        positive_numbers = (
            "rates_ttl_seconds",
            "request_timeout",
            "update_interval_seconds",
        )

        for key in positive_numbers:
            value = settings[key]

            if type(value) not in (int, float):
                raise ValueError(f"Настройка '{key}' должна быть числом.")

            if not 0 < value < float("inf"):
                raise ValueError(
                    f"Настройка '{key}' должна быть конечной и положительной."
                )

        for key in ("data_dir", "logs_dir"):
            value = settings[key]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Настройка '{key}' должна быть непустой строкой.")

        currency = get_currency(settings["default_base_currency"])
        settings["default_base_currency"] = currency.code
