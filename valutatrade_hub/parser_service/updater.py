"""Получение курсов из источников и обновление хранилища."""

from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError


class RatesUpdater:
    """Координирует API-клиентов и сохранение курсов."""

    def __init__(self, clients, storage):
        """Принимает клиентов источников и хранилище курсов."""
        self._clients = list(clients)
        self._storage = storage

    def run_update(self):
        """Обновляет доступные курсы и сообщает об ошибках источников."""
        updates = []
        errors = []

        for client in self._clients:
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
            except ApiRequestError as error:
                errors.append(f"{client.source}: {error}")

        if not updates:
            details = "; ".join(errors) or "Нет настроенных источников."
            raise ApiRequestError(f"Не удалось обновить курсы. {details}")

        self._storage.save(updates)

        return {
            "updated": len(updates),
            "errors": errors,
        }
