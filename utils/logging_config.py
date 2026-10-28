"""Console and rotating file logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import PROJECT_DIR


def configure_logging(level_name: str = "INFO") -> logging.Logger:
    log_dir = PROJECT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    logger = logging.getLogger("telegram_forwarder")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        Path(log_dir / "forwarder.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger
