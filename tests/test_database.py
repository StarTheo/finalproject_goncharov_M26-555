"""Проверки структуры JSON и сохранности хранилища."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.infra.database import DatabaseManager


class DatabaseTests(unittest.TestCase):
    """Проверяет менеджер на отдельных временных файлах."""

    def setUp(self):
        """Переключает менеджер на временную папку."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.directory = Path(directory.name)
        self.db = DatabaseManager()
        directory_patch = patch.object(self.db, "_data_dir", self.directory)
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def test_missing_rates_returns_empty_snapshot(self):
        """Отсутствующий файл означает пустое хранилище."""
        self.assertEqual(
            self.db.read("rates"),
            {"pairs": {}, "last_refresh": None},
        )

    def test_invalid_rates_structure_is_rejected(self):
        """Неправильная структура вызывает StorageError вместо KeyError."""
        examples = (
            "{}",
            "[]",
            '{"pairs": [], "last_refresh": null}',
            '{"pairs": {}, "last_refresh": 123}',
            '{"pairs": {}, "last_refresh": "2026-11-08T12:00:00"}',
            '{"pairs": {"EUR_USD": {}}, "last_refresh": "2026-11-08T12:00:00+00:00"}',
        )
        path = self.directory / "rates.json"

        for content in examples:
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")

                with self.assertRaises(StorageError):
                    self.db.read("rates")

                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_invalid_json_is_not_overwritten(self):
        """Синтаксическая ошибка не уничтожает исходный файл."""
        path = self.directory / "rates.json"
        content = '{"pairs":'
        path.write_text(content, encoding="utf-8")

        with self.assertRaises(StorageError):
            self.db.read("rates")

        self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_invalid_write_preserves_snapshot(self):
        """Неверные новые данные не заменяют корректный снимок."""
        snapshot = {"pairs": {}, "last_refresh": None}
        self.db.write("rates", snapshot)
        path = self.directory / "rates.json"
        before = path.read_bytes()

        with self.assertRaises(StorageError):
            self.db.write("rates", {})

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])
