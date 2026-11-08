"""Декораторы и кэширование результатов."""

from copy import deepcopy
from time import monotonic

MAX_CACHE_ENTRIES = 128


def create_cacher(ttl_seconds):
    """Создаёт независимый кэш с ограниченным временем хранения."""
    cache = {}

    def cache_result(key, value_func):
        """Возвращает сохранённый результат или вычисляет новый."""
        now = monotonic()

        if key in cache:
            saved_at, value = cache[key]

            if now - saved_at < ttl_seconds:
                return deepcopy(value)

            del cache[key]

        value = value_func()

        if value is not None:
            if len(cache) >= MAX_CACHE_ENTRIES:
                cache.clear()

            cache[key] = (monotonic(), deepcopy(value))

        return deepcopy(value)

    return cache_result
