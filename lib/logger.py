import logging
import os
import sys
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

_initialized_loggers = set()


def get_logger(name: str = "nshop") -> logging.Logger:
    """
    Returns a configured logger that outputs simultaneously to console,
    timestamped log file (logs/run_YYYYMMDD_HHMMSS.log), and logs/latest.log.
    """
    logger = logging.getLogger(name)

    if name in _initialized_loggers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Prevent duplicate messages if root logger has handlers
    logger.propagate = False

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. Timestamped Run Log File (e.g. logs/run_20260822_110500.log)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_log_path = os.path.join(LOGS_DIR, f"run_{run_timestamp}.log")
    file_handler = logging.FileHandler(run_log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 3. Latest Log File (logs/latest.log - overwritten or appended for current run)
    latest_log_path = os.path.join(LOGS_DIR, "latest.log")
    latest_handler = logging.FileHandler(latest_log_path, encoding="utf-8")
    latest_handler.setLevel(logging.DEBUG)
    latest_handler.setFormatter(file_formatter)
    logger.addHandler(latest_handler)

    _initialized_loggers.add(name)
    return logger
