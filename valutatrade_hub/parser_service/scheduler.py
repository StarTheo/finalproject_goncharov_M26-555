"""Отдельный запуск периодического обновления курсов."""

import argparse
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import SOURCE_NAMES, RatesUpdater


def main():
    """Обновляет курсы один раз или с заданным интервалом."""
    parser = argparse.ArgumentParser(description="Планировщик обновления курсов")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--source", choices=tuple(SOURCE_NAMES), default=None)
    args = parser.parse_args()

    settings = SettingsLoader()
    configure_logging(settings)
    config = ParserConfig(settings)
    updater = RatesUpdater(
        [CoinGeckoClient(config), ExchangeRateApiClient(config)],
        RatesStorage(DatabaseManager()),
    )

    try:
        while True:
            try:
                result = updater.run_update(args.source)
                print(f"Обновлено пар: {result['updated']}", flush=True)

                for error in result["errors"]:
                    print(f"Предупреждение: {error}", flush=True)
            except ApiRequestError as error:
                print(f"Ошибка: {error}", flush=True)

                if args.once:
                    return 1

            if args.once:
                return 0

            time.sleep(config.update_interval)
    except KeyboardInterrupt:
        print("\nПланировщик остановлен.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
