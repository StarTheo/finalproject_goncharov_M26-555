"""Настройка файловых журналов приложения."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

LOGGER_FILES = {
    "valutatrade.actions": "actions.log",
    "valutatrade.parser": "parser.log",
}


def configure_logging(settings):
    """Настраивает отдельные журналы торговли и обновления курсов."""
    logs_dir = Path(settings.get("logs_dir"))
    logs_dir.mkdir(parents=True, exist_ok=True)

    for logger_name, filename in LOGGER_FILES.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        handler = RotatingFileHandler(
            logs_dir / filename,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
