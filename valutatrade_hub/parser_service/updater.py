"""Получение курсов из источников и обновление хранилища."""

import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError

SOURCE_NAMES = {
    "coingecko": "CoinGecko",
    "exchangerate": "ExchangeRate-API",
}


class RatesUpdater:
    """Координирует API-клиентов и сохранение курсов."""

    def __init__(self, clients, storage):
        """Принимает клиентов источников и хранилище курсов."""
        self._clients = list(clients)
        self._storage = storage

    def run_update(self, source=None):
        """Обновляет доступные курсы и сообщает об ошибках источников."""

        logger = logging.getLogger("valutatrade.parser")
        logger.info("Начало обновления курсов.")

        updates = []
        errors = []

        clients = self._clients

        if source is not None:
            if source not in SOURCE_NAMES:
                raise ValueError(f"Неизвестный источник: {source}.")

            clients = [
                client for client in clients if client.source == SOURCE_NAMES[source]
            ]

        for client in clients:
            try:
                rates = client.fetch_rates()

                if not rates:
                    raise ApiRequestError("Источник не вернул курсы.")

                observed_at = datetime.now(timezone.utc).isoformat()
                source_updates = []

                for pair, rate in rates.items():
                    if type(rate) not in (int, float):
                        raise ApiRequestError("Источник вернул нечисловой курс.")

                    if not 0 < rate < float("inf"):
                        raise ApiRequestError("Источник вернул недопустимый курс.")

                    source_updates.append(
                        {
                            "pair": pair,
                            "rate": float(rate),
                            "updated_at": observed_at,
                            "source": client.source,
                        }
                    )

                updates.extend(source_updates)
                logger.info(
                    "Источник %s: получено пар %s.",
                    client.source,
                    len(source_updates),
                )
            except ApiRequestError as error:
                errors.append(f"{client.source}: {error}")
                logger.warning("Источник %s: %s", client.source, error)

        if not updates:
            details = "; ".join(errors) or "Нет настроенных источников."
            logger.error("Обновление отменено: ни один источник не вернул курсы.")
            raise ApiRequestError(f"Не удалось обновить курсы. {details}")

        self._storage.save(updates)
        logger.info(
            "Обновление завершено: пар %s, ошибок источников %s.",
            len(updates),
            len(errors),
        )

        return {
            "updated": len(updates),
            "errors": errors,
        }
