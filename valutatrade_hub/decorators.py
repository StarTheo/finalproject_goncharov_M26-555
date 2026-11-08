"""Декораторы и кэширование результатов."""

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
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


def log_action(action, verbose=False):
    """Записывает результат операции, сохраняя её исключения."""

    def decorator(func):
        """Создаёт обёртку для выбранной операции."""
        function_signature = signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            """Логирует успех или ошибку вызова."""
            arguments = function_signature.bind(*args, **kwargs).arguments
            logger = logging.getLogger("valutatrade.actions")

            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "user_id": arguments.get("user_id"),
                "currency": str(arguments.get("currency_code")),
                "amount": str(arguments.get("amount")),
            }

            try:
                result = func(*args, **kwargs)
            except Exception as error:
                event["status"] = "ERROR"
                event["error_type"] = type(error).__name__
                event["error"] = str(error)
                logger.info(json.dumps(event, ensure_ascii=False))
                raise

            event.update(
                {
                    "status": "OK",
                    "currency": result["currency"],
                    "amount": str(result["amount"]),
                    "rate": str(result["rate"]),
                    "base": "USD",
                    "estimated_usd": str(result["estimated_usd"]),
                }
            )

            if verbose:
                event["before"] = str(result["before"])
                event["after"] = str(result["after"])

            logger.info(json.dumps(event, ensure_ascii=False))
            return result

        return wrapper

    return decorator
