"""
Logging configuration for the trading bot.

Sets up two handlers:
  - RotatingFileHandler  → logs/trading_bot.log  (DEBUG+, detailed)
  - StreamHandler        → stderr                 (WARNING+, concise)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")
MAX_BYTES = 10 * 1024 * 1024   # 10 MB per file
BACKUP_COUNT = 5


def setup_logging(log_dir: str = LOG_DIR) -> logging.Logger:
    """
    Configure root logger for the trading_bot namespace.

    Args:
        log_dir: Directory where log files are written (created if absent).

    Returns:
        The configured ``trading_bot`` logger.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "trading_bot.log")

    logger = logging.getLogger("trading_bot")
    # Guard against duplicate handlers if called more than once
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # --- File handler: captures everything (DEBUG and above) ---
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # --- Console handler: only warnings / errors to keep stdout clean ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.debug("Logging initialised — file: %s", log_path)
    return logger
