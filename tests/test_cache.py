"""Проверки кэширования через замыкание."""

import unittest
from unittest.mock import Mock, patch

from valutatrade_hub.decorators import create_cacher


class CacheTests(unittest.TestCase):
    """Проверяет срок хранения и независимость результатов."""

    def test_cache_expires_and_protects_stored_value(self):
        """Кэш избегает повторного расчёта и обновляется после TTL."""
        calculate = Mock(return_value=[1, 2, 3])

        with patch("valutatrade_hub.decorators.monotonic") as clock:
            clock.return_value = 100
            cacher = create_cacher(ttl_seconds=10)

            first = cacher("demo", calculate)
            first.append(999)
            second = cacher("demo", calculate)

            self.assertEqual(second, [1, 2, 3])
            self.assertEqual(calculate.call_count, 1)

            clock.return_value = 111
            third = cacher("demo", calculate)

            self.assertEqual(third, [1, 2, 3])
            self.assertEqual(calculate.call_count, 2)

    def test_failed_calculation_is_not_cached(self):
        """После ошибки следующий вызов повторяет вычисление."""
        calculate = Mock(side_effect=[ValueError("Ошибка расчёта"), 42])
        cacher = create_cacher(ttl_seconds=10)

        with self.assertRaises(ValueError):
            cacher("demo", calculate)

        self.assertEqual(cacher("demo", calculate), 42)
        self.assertEqual(calculate.call_count, 2)
