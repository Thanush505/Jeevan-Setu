"""
telemetry_simulator/logger.py — Structured logging for the Jeevan Setu Telemetry Simulator.

Provides clear, timestamped log output without exposing secrets.
"""

import logging
import sys

_LOGGER_NAME = 'JeevanSetuSimulator'


def setup_logger(level: str = 'INFO') -> logging.Logger:
    """
    Create and configure the simulator logger.

    Args:
        level: Logging level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(_LOGGER_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Return the existing simulator logger (creates one if needed)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        return setup_logger()
    return logger
