"""Точка входа в приложение ValutaTrade Hub."""

from valutatrade_hub.cli.interface import CLI
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def main():
    """Собирает зависимости и запускает консольный интерфейс."""
    settings = SettingsLoader()
    configure_logging(settings)
    database = DatabaseManager()
    service = TradingService(database, settings)

    config = ParserConfig(settings)
    clients = [
        CoinGeckoClient(config),
        ExchangeRateApiClient(config),
    ]
    updater = RatesUpdater(clients, RatesStorage(database))

    CLI(service, updater).run()


if __name__ == "__main__":
    main()
