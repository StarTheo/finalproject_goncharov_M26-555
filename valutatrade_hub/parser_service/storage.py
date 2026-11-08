"""Сохранение текущих курсов валют и истории обновлений."""

from datetime import datetime, timezone


class RatesStorage:
    """Обновляет снимок курсов и сохраняет историю измерений."""

    def __init__(self, database):
        """Сохраняет переданный менеджер хранилища."""
        self._database = database

    def save(self, updates):
        """Сохраняет полученные измерения, оставляя остальные пары."""
        if not updates:
            return

        snapshot = self._database.read("rates")
        history = self._database.read("exchange_rates")
        known_ids = {record["id"] for record in history}

        for entry in updates:
            pair = entry["pair"]
            updated_at = entry["updated_at"]
            previous = snapshot["pairs"].get(pair)

            if previous is None or self._timestamp(updated_at) >= self._timestamp(
                previous["updated_at"]
            ):
                snapshot["pairs"][pair] = {
                    "rate": entry["rate"],
                    "updated_at": updated_at,
                    "source": entry["source"],
                }

            record_id = f"{pair}_{updated_at}"

            if record_id not in known_ids:
                history.append(
                    {
                        "id": record_id,
                        "pair": pair,
                        "rate": entry["rate"],
                        "timestamp": updated_at,
                        "source": entry["source"],
                    }
                )
                known_ids.add(record_id)

        snapshot["last_refresh"] = datetime.now(timezone.utc).isoformat()

        self._database.write("exchange_rates", history)
        self._database.write("rates", snapshot)

    @staticmethod
    def _timestamp(value):
        """Преобразует строку времени с часовым поясом в дату."""
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            raise ValueError("Время курса должно содержать часовой пояс.")

        return timestamp
